"""Core Audio do Windows via COM/ctypes, sem teclado ou interface gráfica."""
import ctypes as C
import os
import uuid
from skills.base import SkillError


class GUID(C.Structure):
    _fields_ = [("Data1", C.c_uint32), ("Data2", C.c_uint16),
                ("Data3", C.c_uint16), ("Data4", C.c_ubyte * 8)]

    @classmethod
    def parse(cls, text):
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


def check(hr):
    if hr < 0:
        raise SkillError("audio_api_error", "A API de áudio do Windows não concluiu a operação.")


def call(pointer, index, argtypes, *args):
    table = C.cast(pointer, C.POINTER(C.POINTER(C.c_void_p))).contents
    function = C.WINFUNCTYPE(C.c_long, C.c_void_p, *argtypes)(table[index])
    result = function(pointer, *args)
    check(result)
    return result


class AudioEndpoint:
    def __init__(self):
        self.pointers = []
        self.initialized = False

    def __enter__(self):
        if os.name != "nt":
            raise SkillError("windows_required", "Esta skill requer Windows.")
        self.ole = C.WinDLL("ole32")
        self.ole.CoInitializeEx.argtypes = [C.c_void_p, C.c_uint32]
        self.ole.CoInitializeEx.restype = C.c_long
        hr = self.ole.CoInitializeEx(None, 2)
        if hr not in (0, 1, -2147417850):  # já inicializado em outro apartment
            check(hr)
        self.initialized = hr in (0, 1)
        try:
            enumerator = C.c_void_p()
            clsid = GUID.parse("BCDE0395-E52F-467C-8E3D-C4579291692E")
            iid = GUID.parse("A95664D2-9614-4F35-A746-DE8DB63617E6")
            self.ole.CoCreateInstance.argtypes = [C.POINTER(GUID), C.c_void_p, C.c_uint32, C.POINTER(GUID), C.POINTER(C.c_void_p)]
            self.ole.CoCreateInstance.restype = C.c_long
            check(self.ole.CoCreateInstance(C.byref(clsid), None, 23, C.byref(iid), C.byref(enumerator)))
            self.pointers.append(enumerator)
            device = C.c_void_p()
            call(enumerator, 4, [C.c_int, C.c_int, C.POINTER(C.c_void_p)], 0, 1, C.byref(device))
            self.pointers.append(device)
            endpoint = C.c_void_p()
            endpoint_iid = GUID.parse("5CDF2C82-841E-4546-9722-0CF74078229A")
            call(device, 3, [C.POINTER(GUID), C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p)],
                 C.byref(endpoint_iid), 23, None, C.byref(endpoint))
            self.pointers.append(endpoint)
            self.endpoint = endpoint
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def state(self):
        scalar = C.c_float()
        muted = C.c_int()
        call(self.endpoint, 9, [C.POINTER(C.c_float)], C.byref(scalar))
        call(self.endpoint, 15, [C.POINTER(C.c_int)], C.byref(muted))
        return {"volume": round(scalar.value * 100, 1), "muted": bool(muted.value)}

    def set_volume(self, value):
        call(self.endpoint, 7, [C.c_float, C.c_void_p], C.c_float(value / 100), None)

    def set_mute(self, muted):
        call(self.endpoint, 14, [C.c_int, C.c_void_p], int(muted), None)

    def __exit__(self, *args):
        for pointer in reversed(self.pointers):
            table = C.cast(pointer, C.POINTER(C.POINTER(C.c_void_p))).contents
            C.WINFUNCTYPE(C.c_ulong, C.c_void_p)(table[2])(pointer)
        self.pointers.clear()
        if self.initialized:
            self.ole.CoUninitialize()
            self.initialized = False
