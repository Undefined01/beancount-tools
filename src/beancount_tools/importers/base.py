from beancount.parser import parser, printer


class Base:
    def __init__(self, filename, byte_content, entries, option_map):
        raise RuntimeError("Not implemented!")

    def parse(self):
        pass

    def write(self, filename):
        with open(filename, "w", encoding="utf-8") as f:
            printer.print_entries(self.parse(), file=f)
