import time
import argparse
import csv
import json
import operator
import os
import sys
import traceback
import zipfile
import sqlite3
from collections import defaultdict
from typing import List, Dict

import discogs_client
import requests
from music21 import converter, stream, note, chord, text, musicxml, features, key, harmony


def detectGenres(query: str, depth: int, num_of_items: int, client: discogs_client.Client)-> List:
    """ detect genres using discogs client.
    :depth: number of song to be used
    :num_of_items: number of items in the list returned
    :d: discogs client object
    :returns: list of list of tuples:
        [
            [(genre1, occurrences), (genre2, occurrences), ...],
            [(style1, occurrences), (style2, occurrences), ...]
        ]
    """
    r = client.search(query, type='release')

    r = r.sort('year')

    # populate genres_stats list
    genres_stats = defaultdict(int)
    styles_stats = defaultdict(int)
    r.per_page = depth
    l = r.page(1)
    for release in l:
        genres = release.fetch('genre')
        if genres is not None:
            for k in genres:
                genres_stats[k] += 1
        if release.styles is not None:
            for k in release.styles:
                styles_stats[k] += 1

    genres = []
    styles = []
    if len(genres_stats) > 0:
        twoMostCommon(num_of_items, genres_stats, genres)
    if len(styles_stats) > 0:
        twoMostCommon(num_of_items, styles_stats, styles)

    return [genres, styles]


def twoMostCommon(num_of_items, dictionary, listOfTuples):
    for i in range(num_of_items):
        if i < len(dictionary):
            most_common_tuple = max(dictionary.items(),
                                    key=operator.itemgetter(1))
            dictionary.pop(most_common_tuple[0])
            listOfTuples.append(most_common_tuple)


def getComposerInfoByUri(uri: str) -> Dict:
    """:returns: same as @getComposerInfoByName"""

    r = requests.get(uri, params={'format': 'json'})
    data = json.loads(r.text)
    if checkingErrors(data):
        return getComposerInfoByUri(uri)

    composer = {
        'correct_name': data.get('commonName'),
        'home_country': data.get('homeCountry'),
        'birth': formatDate(data.get('birthDate')),
        'death': formatDate(data.get('deathDate'))
    }

    return composer


def getComposerInfoByName(name: str) -> Dict:
    """ :retuns: a dictionary containing the birth date, the death date, the
    actual name and the nationality of the composer
    """

    url = 'https://secondhandsongs.com/search/artist'

    params = {
        'format': 'json',
        'commonName': name
    }

    resp = requests.get(url=url, params=params)
    data = json.loads(resp.text)
    if checkingErrors(data):
        return getComposerInfoByName(name)

    if len(data.get('resultPage') or '') == 0:
        return None
    artist_page = data['resultPage'][0]['uri']
    return getComposerInfoByUri(artist_page)


def formatDate(date) -> str:
    if date is None:
        return None
    tokens = str(date).split('-', 3)
    returned = ''
    if len(tokens) == 1:
        returned = tokens[0] + '-00-00'
    elif len(tokens) == 2:
        returned = tokens[0] + '-' + tokens[1] + '-00'
    else:
        returned = tokens[0] + '-' + tokens[1] + '-' + tokens[2]

    return returned


def getWorkInfo(title: str, composer: str) -> Dict:
    """ :returns: a dict with work info """
    url = 'https://secondhandsongs.com/search/work'

    params = {
        'format': 'json',
        'credits': composer,
        'title': title
    }

    resp = requests.get(url=url, params=params)
    data = json.loads(resp.text)

    if checkingErrors(data):
        return getWorkInfo(title, composer)

    if len(data.get('resultPage') or '') == 0:
        return None

    work_page = data['resultPage'][0]['uri']
    r = requests.get(work_page, params={'format': 'json'})
    data = json.loads(r.text)

    if checkingErrors(data):
        return getWorkInfo(title, composer)

    all_authors = []
    for i in data.get('credits'):
        all_authors.append(i.get('uri'))

    work = {
        'language': data.get('language'),
        'correct_title': data.get('title'),
        'correct_credits_uri': all_authors,
    }

    if data.get('original') is not None:
        original_performance_page = data['original'].get('uri')
        r = requests.get(original_performance_page,
                         params={'format': 'json'})
        data = json.loads(r.text)
        if checkingErrors(data):
            return getWorkInfo(title, composer)
        work['original_performance_date'] = formatDate(data.get('date'))
    else:
        work['original_performance_date'] = None

    return work


def getTonality(score: stream.Score)-> key.Key:
    """ :returns: a key.Key object representing tonality detected by Krumhanslschumckler
    algorithm, only if its 'tonalCertainty()' is >= 0.9, None otherwise
    """
    try:
        estimated = score.analyze('key.krumhanslschmuckler')
    except Exception:
        return None

    if estimated.tonalCertainty() < 0.9:
        return None
    else:
        return estimated


def scoreIsCompatible(s: stream.Score) -> bool:
    """ parse a s and returs True if it is compatible with our symbolic
    representation system

    This also sets the 'timeSignature', 'keySignature', 'incipitType' and
    'hasTriplets' in compatible stream.Score objects
    """
    # no multiple voices are allowed
    print('checking compatibility...')
    sc = s.explode()

    # only one part is allowed
    print('\tchecking parts (only one allowed)...')
    if hasattr(sc, 'parts'):
        if len(sc.parts) > 1:
            return False

    # only one key signature is allowed
    print('\tchecking key signatures (only one allowed)...')
    signatures = s.flat.getKeySignatures()
    if len(signatures) > 1:
        for signature in signatures:
            if signature.asKey().name != signatures[0].asKey().name:
                return False

    # looking for the right tonality
    estimated = getTonality(s)
    if estimated is not None:
        s.keySignature = estimated.asKey()
    elif len(signatures) == 0:
        return False
    else:
        s.keySignature = signatures[0].asKey()

    # only one time signature is allowed
    print('\tchecking time signatures (only one allowed)...')
    signatures = s.flat.getTimeSignatures()
    if len(signatures) > 1:
        for signature in signatures:
            if signature.ratioString != signatures[0].ratioString:
                return False
    elif len(signatures) == 0:
        return False

    measure_length = signatures[0].numerator / signatures[0].denominator * 4
    s.timeSignature = signatures[0]

    # no multiple white measures in incipit
    # setting incipit type
    print('\tchecking no multiple white measures at the beginning...')
    for m in s.recurse().getElementsByClass(stream.Measure):
        if len(m.recurse().getElementsByClass(note.Note)) == 0:
            m.containerHierarchy()[0].remove(m)
        else:
            n = m.recurse().getElementsByClass(note.Note)[0]
            if n.offset > 0:
                s.incipitType = 'acefalo'
            elif m.duration.quarterLength < measure_length:
                s.incipitType = 'anacrusi'
            else:
                s.incipitType = 'tetico'
            break

    # no multiple white measures at the end
    print('\tchecking no multiple white measures at the end...')
    it = s.recurse().getElementsByClass(stream.Measure)
    for m in reversed(it):
        if len(m.recurse().getElementsByClass(note.Note)) == 0:
            m.containerHierarchy()[0].remove(m)
        else:
            break

    print('\tchecking triplets and chords...')
    s.hasTriplets = False
    noChordSymbol = True
    it = s.flat.notesAndRests
    i = 0
    while i < len(it):
        n = it[i]
        if type(n) is harmony.ChordSymbol:
            noChordSymbol = False
            i += 1
            continue

        # no written chords allowed
        if type(n) is chord.Chord:
            print('----Chords are not allowed----')
            return False

        # triplets checking:
        if len(n.duration.tuplets) > 0:
            tuplet = n.duration.tuplets[0]

            # only triplets are allowed
            if tuplet.numberNotesActual > 3:
                print('----Only triplets are allowed----')
                return False

            # the following is to check the nesting level
            if tuplet.nestedLevel > 1:
                print('----only one nested level is allowed----')
                return False

            # only if it is contained in one measure
            if tuplet.totalTupletLength() > measure_length:
                print('----tuplets are allowed only in the same measure----')
                return False

            s.hasTriplets = True
            i += 3
        else:
            i += 1

    if noChordSymbol:
        print('----No chords annotated----')
        return False

    return True


def copyToDir(s: stream.Score, dir: str):
    path = os.path.join(dir, s.metadata.composer +
                        '-' + s.metadata.title + '.xml')
    s.write(fp=path)


def fixStrangeCharacters(title, composer):
    composer = composer.translate(
        {ord(c): " " for c in "!@#$%^&*()[]{};:,./<>?\|~-=_+"})
    composer = composer.translate(
        {ord(c): "'" for c in "`"})
    title = title.translate(
        {ord(c): " " for c in "@#$%^&*()[]{};:./<>\|~-=_+"})
    title = title.translate(
        {ord(c): "'" for c in "`"})
    return title, composer


def writeCompressedMxl(xml: str, filename_without_extension: str,
                       filepath_without_extension: str):
    zf = zipfile.ZipFile(filepath_without_extension + '.mxl', mode='w',
                         compression=zipfile.ZIP_DEFLATED)
    zi = zipfile.ZipInfo('META-INF' + os.sep + 'container.xml')
    zi.external_attr = 0o660 << 16
    zf.writestr(zi,
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<container><rootfiles><rootfile full-path='{0}.xml'/>"
                "</rootfiles></container>".format(filename_without_extension))
    zi = zipfile.ZipInfo(filename_without_extension + '.xml')
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o660 << 16
    zf.writestr(zi, xml)

    zf.close()


def checkingErrors(response: Dict):
    # checking errors
    error = response.get('error')
    if error is not None:
        if error.get('code') == 10007:
            print('too many requests... wait a bit and retry')
            time.sleep(30)
            return True
    return False


def secondHandSongsInfo(s: stream.Score):
    """ Queries secondhandsongs.com to gather work and composers info
    :returns: a list containing work and composers dictionaries
    """
    title = s.metadata.title
    composer = s.metadata.composer
    if title == '' or title is None or composer == '' or composer is None:
        return {}, []
    # removing strange characters
    title, composer = fixStrangeCharacters(title, composer)

    # trying to get work info
    print('querying secondhandsongs.com for work and artists info...')
    work = getWorkInfo(title, composer)
    if work is None:
        author = getComposerInfoByName(composer)
        if author is not None:
            work = getWorkInfo(title, author)
    if work is None:
        work = getWorkInfo(title, composer.split(None, 1)[0])
    if work is None:
        work = getWorkInfo(title, '')
    if work is None:
        return {}, []

    # trying to get composers info
    composers = []
    for uri in work.get('correct_credits_uri'):
        composers.append(getComposerInfoByUri(uri))

    return work, composers


def collectData(s: stream.Score, new_dataset_dir: str, id: int, filename: str):
    """ :returns: a dictionary containing 'name of table': 'entry as tuple'
    or None if it is untreatable
    """
    # collecting data
    print('collecting data...')
    work, composers = secondHandSongsInfo(s)

    if 'correct_title' in work and len(composers) > 0:
        # getting genres and styles
        print('querying discogs for genre detection...')
        discogs_query = work.get('correct_title') or ''
        for c in composers:
            correct_name = c.get('correct_name') or ''
            discogs_query += ' ' + correct_name

        if discogs_query == '':
            genres = styles = []
        else:
            genres, styles = detectGenres(
                discogs_query, depth=5, num_of_items=2, client=d)
    else:
        genres = styles = []
        composers.append({'correct_name': '[Unknown]'})
        if s.metadata.title != '':
            work['correct_title'] = s.metadata.title
        else:
            work['correct_title'] = filename.split(
                '_-_', 1)[-1].replace('_', ' ')

    # lyrics
    print('writing lyrics and leadsheet...')
    lyrics = text.assembleAllLyrics(s).replace('\n', '')

    # computing file name
    output_dir = ''
    for c in composers:
        correct_name = c.get('correct_name') or ''
        output_dir += correct_name + '-'

    correct_title = work.get(
        'correct_title').replace(' ', '_').replace('/', '-')
    output_dir = output_dir[:-1].replace(' ', '_')
    output_dir = os.path.join(
        new_dataset_dir, output_dir, correct_title)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_path = os.path.join(output_dir, correct_title)

    # writing lyrics file
    with open(output_path + ".txt", "w") as lyrics_file:
        print(lyrics, file=lyrics_file)

    first_measure = s.recurse().getElementsByClass(stream.Measure)[0].number
    s.measure(first_measure).timeSignature = s.timeSignature
    s.measure(first_measure).keySignature = s.keySignature

    # creating xml string (out is bytes in Py3)
    xml = musicxml.m21ToXml.GeneralObjectExporter(s).parse().decode('utf-8')

    # writing musicxml compressed file
    writeCompressedMxl(xml, work['correct_title'], output_path)

    # getting all features
    print('computing features...')
    f = features.base.allFeaturesAsList(s)

    # writing features csv
    # use features.base.getIndex('name') to get the row index of a certain
    # feature, or something like [x.id for x in features.extractorsById('all')]
    # to get the feature id at the same index position as in the csv
    print('writing features...')
    with open(output_path + '.csv', 'a') as features_file:
        writer = csv.writer(features_file)
        writer.writerows(f[0])
        writer.writerows(f[1])

    # creating output dictionary
    data = createDataDictionary(
        id, work, output_path, s, genres, styles, composers)

    return data


def createDataDictionary(id, work, output_path, s, genres, styles, composers):
    data = {
        'works': [(id, work.get('correct_title'),
                   work.get('original_performance_date'),
                   work.get('language'), output_path + '.txt',

                   output_path + '.mxl')],
        'features': [(id, s.timeSignature.ratioString, s.keySignature.name,
                      s.incipitType, s.hasTriplets, output_path + '.csv')],
        'authors': [],
        'work_genres': [],
        'work_style': [],
        'work_author': []
    }

    for genre in genres:
        data['work_genres'].append((id, genre[0], genre[1]))

    for style in styles:
        data['work_style'].append((id, style[0], style[1]))

    for composer in composers:
        # here 'correct_name' is used twice because the second is needed to
        # check that this author is not already inserted
        data['authors'].append((composer.get('correct_name'), composer.get('birth'),
                                composer.get('death'), composer.get(
                                    'home_country'),
                                composer.get('correct_name')))
        data['work_author'].append((id, composer.get('correct_name')))
    return data


class DBInterface():

    """ A class to interface to the SQLite Database """

    temp_data = {
        'works': [],
        'features': [],
        'authors': [],
        'work_author': [],
        'work_genres': [],
        'work_style': []
    }

    counter = 0

    def firstIndex(self):
        """ get the first available index of a work """
        self.cursor.execute('select max(id) from works')
        i = self.cursor.fetchone()[0]
        if i is not None:
            i += 1
        else:
            i = 0
        return i

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __init__(self, path_to_db):
        """ creates a new db at :path_to_db address using file named
        'db_creation.sql' as starting point """

        try:
            self.connection = sqlite3.connect(path_to_db)
            self.cursor = self.connection.cursor()

            print("Reading SQL Script...")

            scriptfilename = 'db_creation.sql'
            scriptFile = open(scriptfilename, 'r')
            script = scriptFile.read()
            scriptFile.close()
            self.cursor.executescript(script)
            self.connection.commit()
        except Exception:
            print("can't create db... exiting")
            traceback.print_exc()
            sys.exit(3)

    def addToDB(self, data):
        """ add data to the database """
        for k in data.keys():
            self.temp_data[k] += data[k]

        self.counter += 1
        if self.counter == 10:
            self.__commitData()
            self.counter = 0

    def __commitData(self):
        print("____________ WRITING DATA TO DB _____________")

        self.cursor.executemany(
            'INSERT INTO works VALUES (?, ?, ?, ?, ?, ?)', self.temp_data['works'])

        self.cursor.executemany(
            'INSERT INTO authors SELECT ?, ?, ?, ? WHERE NOT EXISTS \
            (SELECT 1 FROM authors WHERE common_name = ?)',
            self.temp_data['authors'])

        self.cursor.executemany(
            'INSERT INTO features VALUES (?, ?, ?, ?, ?, ?)', self.temp_data['features'])

        self.cursor.executemany(
            'INSERT INTO work_author VALUES (?, ?)', self.temp_data['work_author'])

        self.cursor.executemany(
            'INSERT INTO work_genres VALUES (?, ?, ?)', self.temp_data['work_genres'])

        self.cursor.executemany(
            'INSERT INTO work_style VALUES (?, ?, ?)', self.temp_data['work_style'])

        try:
            self.connection.commit()
        except Exception:
            print("can't write to db... exiting")
            traceback.print_exc()
            sys.exit(3)

        for k in self.temp_data.keys():
            self.temp_data[k] = []

    def __del__(self):
        self.__commitData()
        self.connection.close()


def main(dbManager):

    # loading file names
    parser = argparse.ArgumentParser()

    parser.add_argument("--dir", "-d", type=str, required=True)
    args = parser.parse_args()
    if not os.path.isdir(args.dir):
        print('Directory ' + args.dir + ' does not exists!')
        sys.exit(2)

    new_dataset_dir = 'dataset'
    if not os.path.exists(new_dataset_dir):
        os.makedirs(new_dataset_dir)

    filenames = os.listdir(args.dir)

    exception_dir = 'exception_dir'
    if not os.path.exists(exception_dir):
        os.makedirs(exception_dir)

    not_compatible_dir = 'not_compatible'
    if not os.path.exists(not_compatible_dir):
        os.makedirs(not_compatible_dir)

    id = dbManager.firstIndex()
    for filename in filenames:
        print('------------------------------------')
        print('analysing ' + filename)
        # opening file
        pathname = os.path.join(args.dir, filename)
        if not os.path.isfile(pathname):
            continue

        s = None
        try:
            s = converter.parse(pathname)
        except KeyboardInterrupt:
            return
        except Exception:
            print('invalid file' + pathname)
            continue

        try:
            if scoreIsCompatible(s):
                data = collectData(s, new_dataset_dir, id, filename)
                if data is None:
                    composer_title_unknown_dir = 'unknown'
                    if not os.path.exists(composer_title_unknown_dir):
                        os.makedirs(composer_title_unknown_dir)
                    copyToDir(s, composer_title_unknown_dir)
                else:
                    id += 1
                    print('adding score number ', id)
                    dbManager.addToDB(data)
                os.remove(pathname)
            else:
                os.remove(pathname)
        except Exception as e:
            log_filename = os.path.join(exception_dir, filename)
            s.write(fp=log_filename + '.xml')
            with open(log_filename + ".log", "w") as log_file:
                print(traceback.format_exc(), file=log_file)


d = discogs_client.Client(
    'SMC application', user_token="xtZDGNZBTszqvsqGNHTmLyhKmiHfUpbZuaAETjCR")

dbManager = DBInterface('EWLD.db')
main(dbManager)
del dbManager
