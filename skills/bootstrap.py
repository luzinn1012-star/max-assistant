from automation.audio import AudioEndpoint
from automation.windows import WindowsBackend
from config import ROOT
from skills.apps import AppsSkill, load_apps
from skills.folders import FoldersSkill
from skills.help import HelpSkill
from skills.registry import SkillRegistry
from skills.system import SystemSkill
from skills.volume import VolumeSkill


def build_registry(settings, backend=None, audio=None):
    backend = backend or WindowsBackend(settings.launch_verify_timeout)
    registry = SkillRegistry()
    for skill in (AppsSkill(backend, load_apps(ROOT / "apps.json")), FoldersSkill(backend),
                  VolumeSkill(audio or AudioEndpoint, settings.volume_step),
                  SystemSkill(backend), HelpSkill()):
        registry.register(skill)
    return registry
