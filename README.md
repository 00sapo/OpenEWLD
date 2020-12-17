# 2018 OpenEWLD

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4332855.svg)](https://doi.org/10.5281/zenodo.4332855)


#### Open Enhanced Wikifonia Leadsheet Dataset

**N.B. All content of this repository should be free of copyright. If you think that some score is under copyright and I shouldn't distribute it, please open an issue.**

[federicosimonetta.eu.org](https://federicosimonetta.eu.org)

### What is EWLD

EWLD (_Enhanced Wikifonia Leadsheet Dataset_) is a music leadsheet dataset that comes with a lot of metadata about composers, works, lyrics and features. It is designed for musicological and research purposes.

### What is OpenEWLD

OpenEWLD is a dataset extracted from EWLD containing only public domain scores. You can redistribuite this worl as you want.

### What I have added

This dataset comes from the old Wikifonia archive that is available on the web.
I just filtered its files to get only the ones compatible with algorithm descripted in my thesis that is a graph-based representation of musical scores aimed at computational music analysis, computational musicology and music information retrieval.

Moreover I added some notions taken from secondhandsongs.com and discogs.com, such as the correct title, authors, year of composition, authors' year of birth and death and nationality, language, musical genres and styles. Also, I added a lot of features relative to each music score computed through [music21](http://web.mit.edu/music21/) and I separeted the lyrics where available.

### What should be added

-   lyrics semantic tags (maybe using gensim)
-   delete path to empty lyrics files
-   add other features
-   use additional source info (google, musixmatch, etc.)
-   add path to authors directory
-   switch to extraction from data dumps no connection required
-   add auto language detection
-   correct measure numbering after removing emtpy measures
-   solve bug on key signatures setting: no key signature is saved if setted in highest object hierarchy
-   solve bug on time signatures: method getTimeSignatures() returns '4/4' by default
-   ...

### Database creation

The database was extracted with a python >=3.6 script from the old Wikifonia dataset. You can regenerate it simply launching the script with this command:

    python3 EWLDcreation.py -d <path-to-wikifonia>

You will need a stable internet connection and some python libraries, that you can install using the following command:

    sudo pip3 install discogs_client music21\\
    requests argparse csv json operator os sys\\
    traceback zipfile sqlite3 collections typing\\
    time

Propably, most of them are already installed in your python3 distribution.

If internet connection goes down, you'll find some file in a directory called `exception_dir`. Delete it and rerun the script a few times without changing anything. If exceptions still persist, please, contact me.

Note that the file `db_creation.sql` **must** be in the working directory. It contains the SQL script needed to create the initial tables.

Finally, to create OpenEWLD you have to extract a subset containing only public domain scores by simply running this command from the same directory in which you find this README:

    python3 OpenEWLDcreation.py

### Dataset organization

The database is organized as follows:

-   in the directory called `dataset` you will find a directory for each composer and within it a directory for each score by that composer (or combination of composers). You will also find a directory called `[Unknown]` for all scores without a recognized composer.
-   in the directory `except_dir`, if it exist there will be scores and logs relative to files that cannot be parsed correctly
-   in the file `EWLD.db` you will find a SQLite3 database which contains all metatags and file path

Note that all scores are filtered and edited so that they have the following properties:

-   only one key signature and only one time signature (but they may not be there - see [_what should be added_](#what-should-be-added))
-   no `strong` modulations (see paragraph about `tonality` field in the `features` table of the db)
-   any triplet is allowed but not other tuplet, no nested and not between different measures (_N.B. I thought to have removed tuplets with notes of different values, but actually they could still be there, see line 276 of the creation script_)
-   the tonality is expressed in the MusicXML
-   chords symbol (harmony) are always annotated in the MusicXML
-   only one voice is present in the score, no secondary voices or chords are allowed
-   no multiple white measures at beginning or at the end of the segment

### Database structure

The database `EWLD.db` is a SQLite3 database. You can use any software to read it, for example [SQLiteStudio](https://sqlitestudio.pl/) which is simple, tiny and portable. With it you can also extract XML, HTML, JSON, SQL and PDF files.

It contains 6 tables, each described in the following paragraphs.

#### `works` table

Each entry represents a work, as stated in secondhandsongs.com. A work is a music composition: it can have several recordings by different performers, but the music opera is only one.

Actually, because of the noisiness of beginning dataset, you could also find entries representing derived works. Most of them should have the authors marked as '[Unknown]'.

Fields are:

-   _id_: unique integer
-   _title_: if author is not 'Unknown' it is the title given by secondhandsongs.com, otherwise it is taken from the original score metadata or from the filename
-   _first_performance_date_: if available, the date of the first performance of the song, as given by secondhandsongs.com. Usually, it should be similar to the composition date
-   _language_: the language as given by secondhandsongs.com or as detected by music21
-   _path_lyrics_: the path to the txt file containing the lyrics (it could be empty)
-   _path_leadsheet_: the path to the compressed MusicXML file containing the leadsheet

#### `authors` table

This represents the authors. Fields are:

-   _commonName_: the name of the author as given by secondhandsongs.com (the real author name is not available through their API at now; homonimy are diversified with ending `[1]`, `[2]`, etc.
-   _birth_: date of birth if available (from secondhandsongs.com)
-   _death_: date of death if available (from secondhandsongs.com)
-   _nationality_ nationality if available (from secondhandsongs.com)

#### `features` table

Each entry describes a work from a musical point of view.

-   _id_: the id of the work
-   _metric_: metric signature as stated in the original score **N.B. This is affected by a bug, sometime 4/4 could appear but it could be wrong, see [what should be added](#what-should-be-added)** 
-   _tonality_: the tonality as detected by _krumhansl-schmuckler_ algorithm (to avoid erroneous notation given by wikifonia users). If the certainty computed by [music21] is not enough high (namely >= 0.9), the one provided in the score is used. This prevents by erroneouses key signatures provided by Wikifonia users. **N.B. a bug in saving score made key detection unuseful, see [what should be added](#what-should-be-added) **
-   _incipit_type_: a string, it can be 'anacrusi', 'acefalo' o 'tetico'
-   _has_triplets_: a boolean that is true if there are triplets
-   _features_path_: path to the csv file containing features computed by music21. Each row is a different feature. You can find a feature given its index, e.g.:
-   with `features.base.getIndex('<name>')` you get the index of a certain feature, that is equal to the row index in the csv file;
-   with `[x.id for x in features.extractorsById('all')]` you can get the list of features id in the same order as in the csv;
-   read more [here](http://web.mit.edu/music21/doc/moduleReference/moduleFeaturesBase.html).

#### `work_author` table

This table is needed to join `works` table and  `author` table

#### `work_genres` and `work_styles` tables

These tables give to each work a style and genre classification in a 2D space with a fuzzy approach. By example, a work genre could be identified by a 2D vector ('rock', 'pop'). Each entry of these tables represent an entry of the vector.
Also, each entry of the vector is associated with a `occurrences` field that models the certainty of that genre for that work.
A good way to infer genre and/or style of work is to check if one of the two vector entries has more than twice occurences of the other. If yes, you could consider it as genre or style of the work, otherwise you can represent its genre/style using two coordinates.

These tables create association between a work and genres derived by discogs.com following this procedure:

-   for each work creates a query made by _`title` `composer1` `composer2`_ `etc.`
-   consider the top-10 releases ordered by year returned by discogs.com:
-   takes histogram of genres and styles, following `discogs` categorization
-   for each work, memorize the two most common genres and the two most common styles

## Licenses

-   Part of the database coming from discogs.com (namely genres and styles info) is released under [CC0](https://creativecommons.org/publicdomain/zero/1.0/) license.

-   Part of the database coming from secondhandsongs.com (namely authors info, works titles and performance date) is released under [CC BY-NC 3.0](https://creativecommons.org/licenses/by-nc/3.0/).

-   Compressed MusicXML files and Lyrics files are intended to contain only Public Domain content.

-   The remaining part of this software, included database info, is released under MIT license:


    Copyright (c) 2018, Federico Simonetta, [federicosimonetta.eu.org](http://federicosimonetta.eu.org)

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
    OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
    OTHER DEALINGS IN THE SOFTWARE.

### Cite us

Simonetta, Federico and Carnovalini, Filippo and Orio, Nicola and Rodà, Antonio. Symbolic Music Similarity through a Graph-based Representation. Proceedings of the Audio Mostly 2018 on Sound in Immersion and Emotion - AM'18. ACM Press, Year 2018. 
