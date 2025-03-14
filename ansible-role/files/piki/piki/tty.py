import sys

# https://urwid.org/index.html
# https://urwid.org/tutorial/index.html

import urwid

palette = [
    ("banner", "black", "light gray"),
    ("streak", "black", "dark red"),
    ("bg", "black", "dark blue"),
]

txt = urwid.Text(("banner", " PiKi: Raspberry [Pi Ki]osk "), align="center")
map1 = urwid.AttrMap(txt, "streak")
fill = urwid.Filler(map1)
map2 = urwid.AttrMap(fill, "bg")

def main():
    loop = urwid.MainLoop(map2, palette)
    loop.run()
