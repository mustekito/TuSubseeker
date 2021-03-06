#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from libs import Parser
from libs import ShowInfo
from libs import Printer
import argparse
import downloader
import json
import os
import sys

standalone_episode_regexs = [
    # Newzbin style, no _UNPACK_
    '(.*?)( \(([0-9]+)\))? - ([0-9]+)+x([0-9]+)' +
    '(-[0-9]+[Xx]([0-9]+))?( - (.*))?',
    # standard s00e00
    '(.*?)( \(([0-9]+)\))?[Ss]([0-9]+)+' +
    '[Ee]([0-9]+)(-[0-9]+[Xx]([0-9]+))?( - (.*))?'
]

episode_regexps = [
    # S03E04-E05
    '(?P<show>.*?)[sS](?P<season>[0-9]+)[\._ ]' +
    '*[eE](?P<ep>[0-9]+)[\._ ]*([- ]?[sS](?P<second' +
    'Season>[0-9]+))?([- ]?[Ee+](?P<secondEp>[0-9]+))?',
    # S03-03
    '(?P<show>.*?)[sS](?P<season>[0-9]{2})' +
    '[\._\- ]+(?P<ep>[0-9]+)',
    # 3x03, 3x03-3x04, 3x03x04
    '(?P<show>.*?)([^0-9]|^)(?P<season>(19[3-9][0-9]|20[0-5][0-9]' +
    '|[0-9]{1,2}))[Xx](?P<ep>[0-9]+)((-[0-9]+)?[Xx](?P<secondEp>[0-9]+))?',
    # SP01 (Special 01, equivalent to S00E01)
    '(.*?)(^|[\._\- ])+(?P<season>sp)(?P<ep>[0-9]{2})([\._\- ]|$)+',
    # .602.
    '(.*?)[^0-9a-z](?P<season>[0-9]{1,2})(?P<ep>[0-9]{2})' +
    '([\.\-][0-9]+(?P<secondEp>[0-9]{2})([ \-_\.]|$)[\.\-]?)?([^0-9a-z%]|$)'
]

release_equivalence_table = {
    'LOL': 'DIMENSION',
    'SYS': 'DIMENSION',
    'XII': 'IMMERSE',
    'PROPER': 'LOL,DIMENSION',
    'DIMENSION': 'LOL'
}

lang_codes = {
    '1': 'en',
    '5': 'es',
    '6': 'es-la'
}

lang_codes_rev = {
    'en': '1',
    'es': '5',
    'es-la': '6'
}


def folderSearch(folder):
    printer.warningPrint("Feature not finished. May be (it sure is) buggy.")
    printer.infoPrint("Buscando mkv's en: " + folder)
    filename = ""
    remove = ""
    fileset = set()
    already_downloaded = set()
    languages = ["en", "es"]

    for file in os.listdir(folder):
        if file.endswith(".mkv"):
            filename = str(file)
            remove = os.path.splitext(os.path.basename((folder + filename)))[1]
            fileset.add(filename[:-len(remove)])
        if file.endswith(".srt"):
            filename = str(file)
            remove = os.path.splitext(os.path.basename((folder + filename)))[1]
            filename = filename[:-len(remove)]

            for item in languages:
                if filename.endswith('.' + item):
                    remove = 3
                    filename = filename[:-remove]
                    already_downloaded.add(filename)

    if len(fileset) == 0:
        printer.infoPrint("No files left to process or the " +
                          "folder does not contain any mkv")

    for mkvfile in fileset:
        if mkvfile not in already_downloaded:
            for rx in episode_regexps[0:-1]:
                match = re.search(rx, mkvfile, re.IGNORECASE)
                if match:
                    show = match.group('show')
                    release = mkvfile[mkvfile.rfind('-') + 1:]
                    if release.rfind('[') > -1:
                        release = release[0:release.rfind('[')]

                    # Se convierte a int para quitar los 0 de delante.
                    # El formato de tusubtitulo.com es 'Show 1x01'
                    season = match.group('season')
                    episode = match.group('ep')
                    # Clean title.
                    name, year = Parser.cleanName(show)
                    if year is not None:
                        name = "%s %s" % (name, year)
                    showInfo = ShowInfo.ShowInfo(name, int(season),
                                                 episode, release)
                    downloadSubtitle(showInfo, mkvfile)


def langCode(langs):
    langsToLook = []
    if not isinstance(langs, list):
        langsToLook.append(lang_codes_rev[langs])
    else:
        for language in langs:
            langsToLook.append(lang_codes_rev[language])
    return langsToLook

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--title', metavar="Title",
                        default=None)
    parser.add_argument('-s', '--season', metavar="Season",
                        default=None)
    parser.add_argument('-e', '--episode', metavar="Episode",
                        default=None)
    parser.add_argument('-r', '--release', help='Encoder of the release',
                        metavar="Release", default=None)
    parser.add_argument('-f', '--folder', help='Folder that contains ' +
                        'the mkv files', metavar="Folder", default='.')
    parser.add_argument('-l', '--languages', help='Languages in which the ' +
                        'subtitles are going to be downloaded', nargs='+',
                        metavar="Lang", default=None)
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Enables Debug mode (Verbose)', default=False)
    # MODO output: le pasas un directiorio, y guarda el subtitulo con el nombre
    # del mkv que se encuentre en el directorio
    parser.add_argument('-o', '--output', help='Folder where will be saved ' +
                        'the srt files', metavar="Output", default='.')
    args = parser.parse_args()

    printer = Printer.Printer(args.debug)

    if len(sys.argv) > 1 and args.folder is ".":
        printer.debugPrint("Normal mode detected")
        printer.debugPrint("Checking all required arguments are present")
        isItFolderSearch = False
        argStatus = []
        for arg in vars(args):
            if getattr(args, arg) is None and arg is not 'release' \
                    and arg is not 'languages':
                parser.error("Argument '--{}' is required for normal search"
                             .format(arg))
                sys.exit(-1)
    else:
        printer.debugPrint("Folder Search mode detected")
        isItFolderSearch = True

    langs_list = None
    if args.languages is None:
        with open("languages.json") as langs_file:
            langs = json.load(langs_file)

        langs_list = langs["languages"]
    else:
        langs_list = args.languages

    printer.debugPrint(args.languages)
    downloader = downloader.Downloader(langCode(langs_list), printer)

    if isItFolderSearch:
        folderSearch(args.folder)
    else:
        episode = args.episode
        if len(args.episode) == 1:
            episode = '0' + episode
        showInfo = ShowInfo.ShowInfo(args.title, args.season,
                                     episode, args.release)
        subtitles = downloader.download(showInfo)
        for sub in subtitles:
            downloader.writeToSrt(sub)
