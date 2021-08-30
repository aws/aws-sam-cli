from jinja2 import Environment, FileSystemLoader, select_autoescape
import yaml
import tempfile
import filecmp
import shutil
import sys


def main():
    env = Environment(loader=FileSystemLoader(""), autoescape=select_autoescape(), keep_trailing_newline=True)

    def kebab_case(s):
        return s.replace(" ", "-")

    def camel_case(s):
        return "".join(w[0].upper() + w[1:] for w in s.split(" "))

    env.filters["kebab_case"] = kebab_case
    env.filters["camel_case"] = camel_case

    with open("targets.yaml") as f:
        targets = yaml.safe_load(f)

    changed = False
    for file in ("Makefile", "Make.ps1", "appveyor.yml"):
        template = env.get_template(f"{file}.jinja")
        with tempfile.NamedTemporaryFile(mode="w") as f:
            f.write(template.render(notice="WARNING! Do not make changes in this file.", targets=targets))
            f.flush()
            if filecmp.cmp(f.name, file):
                print(f"{file} unchanged")
            else:
                changed = True
                print(f"{file} updated")
                shutil.copyfile(f.name, file)
    if changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
