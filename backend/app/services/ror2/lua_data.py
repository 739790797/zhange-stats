"""Scribunto 数据模块里用到的那一小段 Lua：赋值、表、字符串。"""

from __future__ import annotations

from typing import Any


class LuaModuleError(ValueError):
    """模块正文不是预期的数据表。"""


class _Parser:
    def __init__(self, src: str) -> None:
        self.s = src.lstrip("\ufeff")
        self.n = len(self.s)
        self.i = 0
        self.env: dict[str, Any] = {}

    def parse(self) -> dict[str, Any]:
        while True:
            self._skip()
            if self.i >= self.n:
                break
            self._statement()
        return self.env

    def _statement(self) -> None:
        if self._consume_keyword("return"):
            self.env["return"] = self._parse_value()
            self._consume_semi()
            return
        if self._consume_keyword("function"):
            self._fail("数据模块里出现了函数")
        self._consume_keyword("local")
        name = self._read_ident()
        self._skip()
        if self._peek() == ".":
            self.i += 1
            field = self._read_ident()
            self._skip()
            self._expect("=")
            self._put_field(name, field, self._parse_value())
        elif self._peek() == "[":
            self.i += 1
            key = self._parse_value()
            self._skip()
            self._expect("]")
            self._skip()
            self._expect("=")
            self._put_field(name, key, self._parse_value())
        elif self._peek() == "=":
            self.i += 1
            self.env[name] = self._parse_value()
        else:
            self._fail(f"无法解析语句 {name}")
        self._consume_semi()

    def _put_field(self, name: str, key: Any, value: Any) -> None:
        target = self.env.get(name)
        if target is None:
            target = {}
            self.env[name] = target
        if not isinstance(target, dict):
            self._fail(f"{name} 不是表")
        target[key] = value

    def _parse_value(self) -> Any:
        self._skip()
        if self.i >= self.n:
            self._fail("缺值")
        ch = self.s[self.i]
        if ch in "\"'":
            return self._parse_short_string()
        if self._long_level() is not None:
            return self._parse_long_string()
        if ch == "{":
            return self._parse_table()
        if ch == "-" or ch.isdigit():
            return self._parse_number()
        if self._is_ident_start(ch):
            ident = self._read_ident()
            if ident == "true":
                return True
            if ident == "false":
                return False
            if ident == "nil":
                return None
            if ident not in self.env:
                # 模块里有未声明的标记，例如 Category = { Masterless }。保留这个名字，不把整份模块判失败。
                return ident
            return self.env[ident]
        self._fail("无法解析的值")
        return None

    def _parse_table(self) -> dict[Any, Any] | list[Any]:
        self._expect("{")
        sequential: list[Any] = []
        keyed: dict[Any, Any] = {}
        while True:
            self._skip()
            if self._peek() == "}":
                self.i += 1
                break
            if self._long_level() is not None:
                sequential.append(self._parse_long_string())
            elif self._peek() == "[":
                self.i += 1
                key = self._parse_value()
                self._skip()
                self._expect("]")
                self._skip()
                self._expect("=")
                keyed[key] = self._parse_value()
            elif self._looks_like_field():
                key = self._read_ident()
                self._skip()
                self._expect("=")
                keyed[key] = self._parse_value()
            else:
                sequential.append(self._parse_value())
            self._skip()
            if self._peek() in ",;":
                self.i += 1
                continue
            if self._peek() == "}":
                continue
            self._fail("表项之后缺逗号或右括号")
        if not keyed:
            return {} if not sequential else sequential
        for index, value in enumerate(sequential, start=1):
            keyed.setdefault(index, value)
        return keyed

    def _parse_short_string(self) -> str:
        quote = self.s[self.i]
        self.i += 1
        out: list[str] = []
        while self.i < self.n:
            ch = self.s[self.i]
            if ch == quote:
                self.i += 1
                return "".join(out)
            if ch == "\\":
                out.append(self._escape())
                continue
            if ch == "\n":
                self._fail("字符串没有结束")
            out.append(ch)
            self.i += 1
        self._fail("字符串没有结束")
        return ""

    def _escape(self) -> str:
        self.i += 1
        if self.i >= self.n:
            self._fail("转义不完整")
        ch = self.s[self.i]
        self.i += 1
        simple = {
            "a": "\a",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "v": "\v",
            "\\": "\\",
            '"': '"',
            "'": "'",
            "\n": "",
        }
        if ch in simple:
            return simple[ch]
        if ch == "z":
            while self.i < self.n and self.s[self.i] in " \t\r\n":
                self.i += 1
            return ""
        if ch == "x" and self.i + 1 < self.n:
            hex_digits = self.s[self.i : self.i + 2]
            self.i += 2
            return chr(int(hex_digits, 16))
        if ch.isdigit():
            digits = ch
            for _ in range(2):
                if self.i < self.n and self.s[self.i].isdigit():
                    digits += self.s[self.i]
                    self.i += 1
                else:
                    break
            return chr(int(digits))
        return ch

    def _parse_long_string(self) -> str:
        level = self._long_level()
        if level is None:
            self._fail("长字符串格式不对")
        self.i += 2 + level
        if self.i < self.n and self.s[self.i] == "\n":
            self.i += 1
        elif self.s.startswith("\r\n", self.i):
            self.i += 2
        close = "]" + ("=" * level) + "]"
        end = self.s.find(close, self.i)
        if end < 0:
            self._fail("长字符串没有结束")
        text = self.s[self.i : end]
        self.i = end + len(close)
        return text

    def _parse_number(self) -> int | float:
        start = self.i
        if self.s[self.i] == "-":
            self.i += 1
        if self.i >= self.n or not self.s[self.i].isdigit():
            self._fail("数字格式不对")
        while self.i < self.n and self.s[self.i].isdigit():
            self.i += 1
        is_float = False
        if self.i < self.n and self.s[self.i] == "." and self.i + 1 < self.n and self.s[self.i + 1].isdigit():
            is_float = True
            self.i += 1
            while self.i < self.n and self.s[self.i].isdigit():
                self.i += 1
        if self.i < self.n and self.s[self.i] in "eE":
            is_float = True
            self.i += 1
            if self.i < self.n and self.s[self.i] in "+-":
                self.i += 1
            if self.i >= self.n or not self.s[self.i].isdigit():
                self._fail("数字指数不对")
            while self.i < self.n and self.s[self.i].isdigit():
                self.i += 1
        text = self.s[start : self.i]
        return float(text) if is_float else int(text)

    def _long_level(self) -> int | None:
        if self.i >= self.n or self.s[self.i] != "[":
            return None
        j = self.i + 1
        level = 0
        while j < self.n and self.s[j] == "=":
            level += 1
            j += 1
        if j < self.n and self.s[j] == "[":
            return level
        return None

    def _looks_like_field(self) -> bool:
        if self.i >= self.n or not self._is_ident_start(self.s[self.i]):
            return False
        j = self.i + 1
        while j < self.n and self._is_ident_char(self.s[j]):
            j += 1
        while j < self.n:
            if self.s[j] in " \t\r\n":
                j += 1
                continue
            if self.s.startswith("--", j):
                if j + 2 < self.n and self.s[j + 2] == "[":
                    return False
                nl = self.s.find("\n", j)
                j = self.n if nl < 0 else nl + 1
                continue
            break
        return j < self.n and self.s[j] == "="

    def _skip(self) -> None:
        while self.i < self.n:
            ch = self.s[self.i]
            if ch in " \t\r\n":
                self.i += 1
                continue
            if self.s.startswith("--", self.i):
                self._skip_comment()
                continue
            break

    def _skip_comment(self) -> None:
        self.i += 2
        saved = self.i
        level = self._long_level()
        if level is None:
            nl = self.s.find("\n", saved)
            self.i = self.n if nl < 0 else nl + 1
            return
        self.i = saved
        close = "]" + ("=" * level) + "]"
        end = self.s.find(close, self.i + 2 + level)
        self.i = self.n if end < 0 else end + len(close)

    def _read_ident(self) -> str:
        self._skip()
        if self.i >= self.n or not self._is_ident_start(self.s[self.i]):
            self._fail("缺名字")
        start = self.i
        self.i += 1
        while self.i < self.n and self._is_ident_char(self.s[self.i]):
            self.i += 1
        return self.s[start : self.i]

    def _consume_keyword(self, word: str) -> bool:
        self._skip()
        end = self.i + len(word)
        if not self.s.startswith(word, self.i):
            return False
        if end < self.n and self._is_ident_char(self.s[end]):
            return False
        self.i = end
        return True

    def _consume_semi(self) -> None:
        self._skip()
        if self._peek() == ";":
            self.i += 1

    def _expect(self, token: str) -> None:
        self._skip()
        if not self.s.startswith(token, self.i):
            self._fail(f"应为 {token}")
        self.i += len(token)

    def _peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    @staticmethod
    def _is_ident_start(ch: str) -> bool:
        return ch.isascii() and (ch.isalpha() or ch == "_")

    @staticmethod
    def _is_ident_char(ch: str) -> bool:
        return ch.isascii() and (ch.isalnum() or ch == "_")

    def _fail(self, msg: str) -> None:
        snippet = self.s[self.i : self.i + 40].replace("\n", "\\n")
        raise LuaModuleError(f"{msg}（位置 {self.i}：{snippet}）")


def parse_lua_module(src: str) -> dict[str, Any]:
    """执行数据模块的顶层赋值，返回变量表。`return` 的值在键 ``return``。"""
    return _Parser(src).parse()
