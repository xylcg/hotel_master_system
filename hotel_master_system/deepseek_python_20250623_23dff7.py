import sqlite3

# 连接数据库
conn = sqlite3.connect('hotel.db')
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())

# 查看某个表的内容
cursor.execute("SELECT * FROM orders;")
print(cursor.fetchall())

# 关闭连接
conn.close()