import importlib
import importlib.metadata


def main():
    print()
    print("Hi! Thanks for using PiKi.")
    print()

    eps = importlib.metadata.distribution(__package__).entry_points
    print("Entry points:")
    print()
    for ep in eps:
        if ep.group == 'console_scripts':
            m = ep.value.split(':', 1)[0]
            m_no_main = m[:-9] if m.endswith('.__main__') else m
            m_doc = importlib.import_module(m).__doc__
            print('  %s OR python3 -m %s : %s' % (ep.name, m_no_main, m_doc))
    print()


if __name__ == '__main__':
    main()
