import io
import os

base = r"C:\Users\HZR\Desktop\若依系统\src\R9\ruoyi-admin\src\main\resources"
app = os.path.join(base, "application.yml")
dev = os.path.join(base, "application-dev.yml")


def read(path):
    return io.open(path, encoding="utf-8").read()


def write(path, text):
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)


lines = read(app).split("\n")


def toggle_after(block):
    for i, line in enumerate(lines):
        if line.strip() == block + ":":
            for j in range(i + 1, min(i + 8, len(lines))):
                if lines[j].strip() == "enable: true":
                    lines[j] = lines[j].replace("enable: true", "enable: false")
                    return True
    return False


assert toggle_after("captcha"), "captcha block not found"
assert toggle_after("tenant"), "tenant block not found"
write(app, "\n".join(lines))

lines = read(dev).split("\n")


def toggle_block(block):
    for i, line in enumerate(lines):
        if line.strip() == block + ":":
            for j in range(i + 1, min(i + 6, len(lines))):
                if lines[j].strip() == "enabled: true":
                    lines[j] = lines[j].replace("enabled: true", "enabled: false")
                    return True
    return False


assert toggle_block("spring.boot.admin.client"), "admin client not found"
assert toggle_block("snail-job"), "snail-job not found"

for i, line in enumerate(lines):
    if "jdbc:mysql://localhost:3306/ry-vue?" in line:
        lines[i] = line.replace("jdbc:mysql://localhost:3306/ry-vue?", "jdbc:mysql://127.0.0.1:13307/ry_r9?")
        lines[i] = lines[i].replace("useSSL=true", "useSSL=false")
    if line.strip() == "p6spy: true":
        lines[i] = line.replace("p6spy: true", "p6spy: false")
    if line.strip() == "username: root":
        for j in range(i + 1, min(i + 3, len(lines))):
            if lines[j].strip() == "password: root":
                lines[j] = lines[j].replace("password: root", "password: ")
                break
    if line.strip() == "spring.data:":
        for j in range(i + 1, min(i + 15, len(lines))):
            if lines[j].strip() == "database: 0":
                lines[j] = lines[j].replace("database: 0", "database: 3")
            if lines[j].strip() == "password: ruoyi123":
                lines[j] = lines[j].replace("password: ruoyi123", "password: ''")
write(dev, "\n".join(lines))
print("patched")
