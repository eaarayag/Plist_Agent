#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migración de remove_this_block.pl a Python.

Usos:
  1) Eliminar bloques filtrando por patron(es):
       python3 remove_this_block.py <plist> -f <patron1> [-f <patron2> ...] [-o salida]

  2) Eliminar un bloque por nombre exacto:
       python3 remove_this_block.py <plist> -b <nombre_bloque> [-o salida]

  3) Eliminar bloques desde un archivo de nombres (comportamiento Perl original):
       python3 remove_this_block.py <plist> -l <archivo_lista> [-o salida]

Descripción:
    Lee un archivo PList y elimina los bloques GlobalPList/PList que coincidan
    con los criterios indicados. Los bloques se eliminan de forma iterativa
    (cada eliminación opera sobre el resultado de la anterior).
    El modo -f permite filtrar por patron(es) sobre los nombres de bloques:
      -f val1 val2   -> elimina bloques que contengan val1 O val2
      -f val1 -f val2 -> elimina bloques que contengan val1 Y val2
"""

import sys
import os
import re
import argparse
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plist_utils import open_file, get_all_block_names, apply_filters


def remove_blocks(buffer: List[str], block_names: List[str]) -> List[str]:
    """
    Recorre 'buffer' una única vez y devuelve una nueva lista sin ningún bloque
    GlobalPList/PList cuyos nombres estén en 'block_names'.

    Parámetros:
        buffer      -- lista de líneas del PList en memoria
        block_names -- nombres de los bloques a eliminar

    Retorna:
        Lista de líneas con todos los bloques indicados eliminados.
    """
    names_set = set(block_names)
    modified: List[str] = []
    flag = False

    for line in buffer:
        if flag:
            if "}" in line:
                flag = False
        else:
            m_global = re.match(r'^\s*GlobalPList\s+(\w+)', line)
            m_plist  = re.match(r'^\s*PList\s+(\w+)', line)
            if m_global and m_global.group(1) in names_set:
                flag = True
            elif m_plist and m_plist.group(1) in names_set:
                pass  # descartar referencia PList al bloque eliminado
            else:
                modified.append(line)

    return modified


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Elimina bloques GlobalPList de un archivo PList."
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
        help="Uno o mas patrones separados por espacio (OR entre ellos). "
             "Repetir -f aplica AND entre grupos. "
             "Ej: -f ddrfmbb0 ddrio -f tatpg -> elimina bloques con (ddrfmbb0 O ddrio) Y tatpg"
    )
    group.add_argument(
        "-b", "--block",
        dest="block",
        metavar="NOMBRE",
        help="Nombre exacto del bloque a eliminar"
    )
    group.add_argument(
        "-l", "--list",
        dest="list_file",
        metavar="ARCHIVO",
        help="Archivo con una lista de nombres de bloques a eliminar (uno por linea)"
    )

    parser.add_argument(
        "-o", "--output",
        dest="output",
        metavar="ARCHIVO",
        default="out_remove_this_block.plist",
        help="Archivo de salida (por defecto: out_remove_this_block.plist)"
    )

    args = parser.parse_args()

    # Cargar el PList completo en memoria
    buffer = open_file(args.plist)

    # Determinar la lista de bloques a eliminar según el modo usado
    if args.filters:
        # Modo filtro: seleccionar nombres que coincidan y luego eliminarlos
        all_names = get_all_block_names(buffer)
        block_names = apply_filters(all_names, args.filters)

        if not block_names:
            print("No se encontraron bloques que coincidan con los filtros indicados.")
            sys.exit(0)

        print("Bloques a eliminar ({0}):".format(len(block_names)))
        for n in block_names:
            print("  " + n)

    elif args.block:
        # Modo nombre exacto
        block_names = [args.block]

    else:
        # Modo archivo de lista
        lines = open_file(args.list_file)
        block_names = [l.strip() for l in lines if l.strip()]

    # Eliminar todos los bloques en una única pasada
    buffer = remove_blocks(buffer, block_names)

    # Escribir el resultado
    with open(args.output, "w", encoding="utf-8") as f_out:
        f_out.writelines(buffer)

    print("\nDone :D\n")
    print("Resultado escrito en: {0}".format(args.output))


if __name__ == "__main__":
    main()
