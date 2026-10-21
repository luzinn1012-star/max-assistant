"""Normalização conservadora; preserva sinais, percentuais e casas decimais."""

import re
import unicodedata


def normalize(text: str) -> str:
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = re.sub(r"[,!?]", " ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:(?:ei|hey|ola) )?max(?:\s+|$)", "", text)
    text = re.sub(r"^(?:por favor\s+)", "", text)
    text = re.sub(r"\s+por favor$", "", text)
    return text.strip()
