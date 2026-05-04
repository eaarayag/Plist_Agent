#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migración de give_me_this_block.pl a Python.

Usos:
  1) Extraer bloques filtrando por patron(es) — reemplaza el alias getglobal + grep:
       python3 give_me_this_block.py <plist> -f <patron1> [-f <patron2> ...] [-o salida]

  2) Extraer un bloque por nombre exacto:
       python3 give_me_this_block.py <plist> -b <nombre_bloque> [-o salida]

  3) Extraer bloques desde un archivo de nombres (comportamiento Perl original):
       python3 give_me_this_block.py <plist> -l <archivo_lista> [-o salida]

Descripción:
    Lee un archivo PList y extrae bloques GlobalPList según los criterios indicados.
    El modo -f incorpora la funcionalidad del alias 'getglobal' con múltiples grep:
      getglobal scan.plist | grep "ddrfmbb0" | grep "tatpg" > list
    equivale a:
      python3 give_me_this_block.py scan.plist -f ddrfmbb0 -f tatpg
"""

import sys
import os
import re
import argparse
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plist_utils import open_file, get_all_block_names, apply_filters


def pop_block(buffer: List[str], plb: str, out_file) -> None:
    """
    Busca en 'buffer' el bloque GlobalPList cuyo nombre coincida con 'plb'
    y escribe sus líneas en 'out_file' hasta encontrar el cierre '}'.

    Parámetros:
        buffer   -- líneas del archivo PList en memoria
        plb      -- nombre exacto del bloque a extraer
        out_file -- archivo de salida abierto en escritura
    """
    flag = False
    pattern = re.compile(r'^\s*GlobalPList\s+' + re.escape(plb) + r'\b')

    for line in buffer:
        if flag:
            out_file.write(line)
            if "}" in line:
                flag = False
                break
        elif pattern.match(line):
            flag = True
            out_file.write(line)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrae bloques GlobalPList de un archivo PList."
    )
    parser.add_argument("plist", help="Archivo PList de entrada")

    # Modos de selección de bloques (mutuamente excluyentes)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-f", "--filter",
        dest="filters",
        metavar="PATRON",
        nargs="+",
        action="append",
        help="Uno o más patrones separados por espacio (OR entre ellos). "
             "Repetir -f aplica AND entre grupos. "
             "Ej: -f ddrfmbb0 ddrio -f tatpg -> (ddrfmbb0 O ddrio) Y tatpg"
    )
    group.add_argument(
        "-b", "--block",
        dest="block",
        metavar="NOMBRE",
        help="Nombre exacto del bloque a extraer"
    )
    group.add_argument(
        "-l", "--list",
        dest="list_file",
        metavar="ARCHIVO",
        help="Archivo con una lista de nombres de bloques a extraer (uno por línea)"
    )

    parser.add_argument(
        "-o", "--output",
        dest="output",
        metavar="ARCHIVO",
        default="output.txt",
        help="Archivo de salida (por defecto: output.txt)"
    )

    args = parser.parse_args()

    # Cargar el PList en memoria
    buffer = open_file(args.plist)

    # Determinar la lista de bloques a extraer según el modo usado
    if args.filters:
        # Modo filtro: equivalente a getglobal | grep ... | grep ...
        all_names = get_all_block_names(buffer)
        block_names = apply_filters(all_names, args.filters)

        if not block_names:
            print("No se encontraron bloques que coincidan con los filtros indicados.")
            sys.exit(0)

        print("Bloques seleccionados ({0}):".format(len(block_names)))
        for n in block_names:
            print("  " + n)

    elif args.block:
        # Modo nombre exacto
        block_names = [args.block]

    else:
        # Modo archivo de lista
        lines = open_file(args.list_file)
        block_names = [l.strip() for l in lines if l.strip()]

    # Extraer y escribir los bloques seleccionados
    with open(args.output, "w", encoding="utf-8") as out:
        for name in block_names:
            pop_block(buffer, name, out)

    print("Resultado escrito en: {0}".format(args.output))


if __name__ == "__main__":
    main()
