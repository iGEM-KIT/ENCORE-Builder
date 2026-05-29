#!/usr/bin/env python3

TYPE_EXTENSIONS = {
    "type0.3": ("ATACGGAAGACAACTCATTCT", "ATACGGAAGACTTCTCGGGAT"),
    "type1.3": ("ATACGGGTCTCTACATTGATAT", "ATACGGGTCTCAACAACATT"),
}


def add_extensions(primer_fw: str, primer_rv: str, ext_type: str = None, ext_fw: str = None, ext_rv: str = None):
    #Fügt 5' Extensions zu den Primer Sequenzen hinzu basierend auf einem vordefinierten Typ
    primer_fw = primer_fw.upper()
    primer_rv = primer_rv.upper()

    if ext_type:
        ext_type = ext_type.lower()
        if ext_type not in TYPE_EXTENSIONS:
            raise ValueError(f"Unknown type: {ext_type}. Allowed: {', '.join(TYPE_EXTENSIONS)}")
        ext_fw, ext_rv = TYPE_EXTENSIONS[ext_type]

    extended_fw = primer_fw if not ext_fw else ext_fw.upper() + primer_fw
    extended_rv = primer_rv if not ext_rv else ext_rv.upper() + primer_rv

    return extended_fw, extended_rv
