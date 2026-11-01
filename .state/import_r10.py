import io

src = r"C:\Users\HZR\Desktop\若依系统\src\R10\db\jeecgboot-mysql-5.7.sql"
dst = r"C:\Users\HZR\Desktop\若依系统\.state\r10.sql"
text = io.open(src, encoding="utf-8", errors="ignore").read()
text = text.replace("CREATE database if NOT EXISTS `jeecg-boot`", "CREATE database if NOT EXISTS `ry_r10`", 1)
text = text.replace("USE `jeecg-boot`;", "USE `ry_r10`;", 1)
io.open(dst, "w", encoding="utf-8", newline="\n").write(text)
print(len(text))
