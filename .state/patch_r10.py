import os
import io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "src", "R10", "jeecg-module-system", "jeecg-system-start",
                 "src", "main", "resources", "application-dev.yml")
lines = io.open(p, encoding="utf-8").read().split("\n")
for i, line in enumerate(lines):
    if "jdbc:mysql://127.0.0.1:3306/jeecg-boot?" in line:
        lines[i] = line.replace("127.0.0.1:3306/jeecg-boot", "127.0.0.1:13307/ry_r10")
    if line.strip() == "url: jdbc:mysql://127.0.0.1:13307/ry_r10?characterEncoding=UTF-8&useUnicode=true&useSSL=false&tinyInt1isBit=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai":
        pass
    if line.strip() == "password: root":
        # datasource master（缩进 10 空格）；注释里的不处理
        if line.startswith("          password:"):
            lines[i] = "          password: ''"
    if line.strip() == "database: 0":
        lines[i] = line.replace("database: 0", "database: 4")
    if line.strip() == "password: ''":
        # redis 密码（缩进 4 空格），datasource 用 10 空格
        if line.startswith("    password:"):
            lines[i] = "    password: ruoyi123"
io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("patched")
