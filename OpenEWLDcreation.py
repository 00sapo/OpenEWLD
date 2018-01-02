import os
import shutil
import sqlite3

maxdate = '1948-00-00'

new_dataset_dir = 'OpenEWLD'
print('taking path of public domain mxl files')
c = sqlite3.connect('EWLD.db')
s = c.cursor()
query = "\
select path_leadsheet \
from work_author join works \
on works.id = work_author.id \
where work_author.author = '[Traditional]' or author not in ( \
    select common_name \
    from authors \
    where death >= '" + maxdate + "' or death is NULL \
    )"

s.execute(query)
pathList = s.fetchall()

print('copying author directories')
for path in pathList:
    author_dir = os.path.dirname(os.path.dirname(path[0]))
    new_author_dir = os.path.join(new_dataset_dir, author_dir)

    if not os.path.exists(new_author_dir):
        shutil.copytree(author_dir, new_author_dir)

print('creating new database')
print("Reading SQL Script...")

scriptfilename = 'db_creation.sql'
scriptFile = open(scriptfilename, 'r')
script = scriptFile.read()
scriptFile.close()
new_db_path = os.path.join(new_dataset_dir, 'OpenEWLD.db')
if os.path.exists(new_db_path):
    os.remove(new_db_path)

new_connection = sqlite3.connect(new_db_path)
new_cursor = new_connection.cursor()
new_cursor.executescript(script)
new_connection.commit()

print('AUTHORS TABLE')
query = " \
select * \
from authors \
where common_name = '[Traditional]' or common_name not in ( \
    select common_name \
    from authors \
    where death >= '" + maxdate + "' or death is NULL \
    )"
s.execute(query)

new_cursor.executemany('INSERT INTO authors SELECT ?, ?, ?, ?', s.fetchall())

print('WORKS TABLE')
query = "\
select works.* \
from work_author join works \
on works.id = work_author.id \
where work_author.author = '[Traditional]' or author not in ( \
    select common_name \
    from authors \
    where death >= '" + maxdate + "' or death is NULL \
    ) \
group by work_author.id"
s.execute(query)

new_cursor.executemany(
    'INSERT INTO works VALUES (?, ?, ?, ?, ?, ?)', s.fetchall())

print('WORK_AUTHOR table')
query = " \
select work_author.* \
from work_author join works \
on works.id = work_author.id \
where work_author.author = '[Traditional]' or author not in ( \
    select common_name \
    from authors \
    where death >= '" + maxdate + "' or death is NULL \
    ) \
group by work_author.id"
s.execute(query)

new_cursor.executemany('INSERT INTO work_author VALUES (?, ?)', s.fetchall())

print('FEATURES TABLE')
query = " \
select features.* \
from work_author join features \
on features.id = work_author.id \
where work_author.author = '[Traditional]' or author not in ( \
    select common_name \
    from authors \
    where death >= '" + maxdate + "' or death is NULL \
    ) \
group by work_author.id"
s.execute(query)

new_cursor.executemany(
    'INSERT INTO features VALUES (?, ?, ?, ?, ?, ?)', s.fetchall())

print('WORK_GENRES')
query = "\
select work_genres.* \
from work_author join work_genres \
on work_genres.id = work_author.id \
where work_author.author = '[Traditional]' or author not in ( \
    select common_name \
    from authors \
    where death >= '" + maxdate + "' or death is NULL \
    ) \
group by work_author.id"

s.execute(query)

new_cursor.executemany('INSERT INTO work_genres VALUES (?, ?, ?)', s.fetchall())

print('WORK_STYLE')
query = "\
select work_style.* \
from work_author join work_style \
on work_style.id = work_author.id \
where work_author.author = '[Traditional]' or author not in ( \
    select common_name \
    from authors \
    where death >= '" + maxdate + "' or death is NULL \
    ) \
group by work_author.id"

s.execute(query)

new_cursor.executemany('INSERT INTO work_style VALUES (?, ?, ?)', s.fetchall())

# closing all
c.close()
new_connection.commit()
new_connection.close()
