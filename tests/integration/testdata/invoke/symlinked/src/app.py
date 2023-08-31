def handler(e, c):
    with open("./linked-file.txt", "r") as file:
        return file.read()
    