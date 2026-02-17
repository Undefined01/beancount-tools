import csv
from collections import namedtuple


def get_object_bql_result(ret):
    """Convert BQL query results to named tuples."""
    rtypes, rvalues = ret
    ret = []
    keys = []
    for k in rtypes:
        keys.append(k[0])
    for v in rvalues:
        d = {}
        i = 0
        for vv in v:
            # 只对数字和None转字符串，保留dict等复杂类型
            if vv is None or isinstance(vv, (int, float)) and not isinstance(vv, bool):
                vv = str(vv)
            d[keys[i]] = vv
            i += 1
        t = namedtuple("Struct", keys)(**d)
        ret.append(t)
    return ret


class DictReaderStrip(csv.DictReader):
    """CSV DictReader that strips whitespace from field names and values."""

    @property
    def fieldnames(self):
        if self._fieldnames is None:
            # Initialize self._fieldnames
            # Note: DictReader is an old-style class, so can't use super()
            csv.DictReader.fieldnames.fget(self)
            if self._fieldnames is not None:
                self._fieldnames = [name.strip() for name in self._fieldnames]
        return self._fieldnames

    def __next__(self):
        if self.line_num == 0:
            # Used only for its side effect.
            self.fieldnames
        row = next(self.reader)
        self.line_num = self.reader.line_num

        # unlike the basic reader, we prefer not to return blanks,
        # because we will typically wind up with a dict full of None
        # values
        while row == []:
            row = next(self.reader)
        row = [element.strip() for element in row]
        d = dict(zip(self.fieldnames, row))
        lf = len(self.fieldnames)
        lr = len(row)
        if lf < lr:
            d[self.restkey] = row[lf:].strip()
        elif lf > lr:
            for key in self.fieldnames[lr:]:
                d[key] = self.restval.strip()
        return d
