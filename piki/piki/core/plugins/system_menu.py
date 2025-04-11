import asyncio
import contextlib
import subprocess

from piki.plugin import Plugin


class SystemMenuPlugin(Plugin):
    def _run(self, args, sudo=False):
        if sudo:
            args = ['sudo', '-n'] + args
        return subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    @contextlib.contextmanager
    def _run_safe_ctx(self):
        try:
            yield
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            self.logger.exception("Subprocess exception", exc_info=e)

    def _run_safe(self, args, sudo=False):
        with self._run_safe_ctx():
            return self._run(args, sudo)

    def _show_log(self):
        async def task():
            with self._run_safe_ctx():
                # TODO: remove hardcoded vts
                self._run(['chvt', '1'])
                await asyncio.sleep(5)
                self._run(['chvt', '7'])
        self.ctl.loop_asyncio.create_task(task())

    def on_ui_create(self):
        self.ctl.ui_menu_setup_root(buttons=[
            ('System', 'piki.menu.system'),
        ])
        self.ctl.ui_menu_setup('piki.menu.system', title='System', buttons=[
            ('Show system log (5 sec.)', self._show_log),
            ('Reset', self.ctl.loop_stop),
            ('Reboot', lambda: self._run_safe(['reboot'], True)),
            ('Power off', lambda: self._run_safe(['poweroff'], True)),
        ])
