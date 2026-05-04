#!/usr/bin/env python3
"""Utilidades compartidas para los scripts de procesamiento de PList."""

import re
import sys
from typing import List


def open_file(file_name: str) -> List[str]:
    """Abre un archivo y devuelve su contenido como lista de líneas."""
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            return f.readlines()
    except FileNotFoundError:
        print(f"Error: no se encontró el archivo '{file_name}'", file=sys.stderr)
        sys.exit(1)


def get_all_block_names(buffer: List[str]) -> List[str]:
    """
    Extrae todos los nombres de bloques GlobalPList del plist.

    Parámetros:
        buffer -- líneas del archivo PList

    Retorna:
        Lista de nombres de bloques GlobalPList encontrados.
    """
    names = []
    for line in buffer:
        m = re.match(r'^\s*GlobalPList\s+(\w+)', line)
        if m:
            names.append(m.group(1))
    return names


def apply_filters(names: List[str], filters: List[List[str]]) -> List[str]:
    """
    Filtra la lista de nombres con lógica AND entre grupos y OR dentro de cada grupo.

    Cada '-f val1 val2' genera un grupo OR: el nombre debe contener val1 O val2.
    Múltiples '-f' aplican AND: todos los grupos deben cumplirse.

    Ejemplos:
      -f ddrfmbb0 ddrio        -> ddrfmbb0 OR ddrio
      -f ddrfmbb0 ddrio -f tatpg -> (ddrfmbb0 OR ddrio) AND tatpg

    Parámetros:
        names   -- lista de nombres de bloques
        filters -- lista de grupos; cada grupo es una lista de patrones OR

    Retorna:
        Lista de nombres que satisfacen todos los grupos.
    """
    result = names
    for filter_group in filters:
        pattern = "|".join(filter_group)
        result = [n for n in result if re.search(pattern, n)]
    return result
