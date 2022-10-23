import sqlite3
import bz2

def ReadDatabase(databaseFile):
    con = sqlite3.connect(databaseFile)
    cur = con.cursor()

    for row in cur.execute("SELECT log_id,log_content FROM logs LIMIT 300"):
        data = bz2.decompress(row[1])
        
        file = open("./input/{}.xml".format(row[0]), "wb")
        file.write(data)
        file.close()
        
    con.close()

ReadDatabase("./db/2011.db")
