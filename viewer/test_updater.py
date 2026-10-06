import subprocess,sys,time
import pytest
from viewer import updater

def test_versions_and_assets():
    assert updater.is_newer('v0.18.1','0.18.0') and not updater.is_newer('v0.18.0','0.18.0') and not updater.is_newer('v0.9.9','0.18.0')
    assert updater.version_tuple('v1.2') is None and not updater.is_newer('nightly')
    release={'assets':[{'name':'Climb-Studio-1.0.0-macOS-arm64.dmg','browser_download_url':'m'},{'name':'Climb-Studio-1.0.0-Windows-x64-setup.exe','browser_download_url':'w'},{'name':'SHA256SUMS.txt','browser_download_url':'s'}]}
    assert updater.pick_assets(release,'-macOS-arm64.dmg')==('Climb-Studio-1.0.0-macOS-arm64.dmg','m','s')
    assert updater.pick_assets({'assets':[]},'-macOS-arm64.dmg')==(None,None,None)

def test_checksum_lookup_and_digest(tmp_path):
    good='a'*64;sums=f'{good}  Climb-Studio-1.0.0-macOS-arm64.dmg\n{"b"*64} *other.exe\nnot a line\n'
    assert updater.expected_digest(sums,'Climb-Studio-1.0.0-macOS-arm64.dmg')==good and updater.expected_digest(sums,'other.exe')=='b'*64
    assert updater.expected_digest(sums,'missing.dmg') is None and updater.expected_digest('xyz  file','file') is None
    f=tmp_path/'f';f.write_bytes(b'abc');assert updater.file_digest(f)=='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'

def test_source_checkout_never_self_updates():
    assert not updater.can_self_update()

@pytest.mark.skipif(sys.platform=='win32',reason='POSIX shell swap script')
def test_mac_swap_waits_for_exit_replaces_bundle_and_relaunches(tmp_path):
    from viewer.platform_runtime import MAC_SWAP
    app=tmp_path/'Climb Studio.app';(app/'Contents').mkdir(parents=True);(app/'Contents'/'old').write_text('old')
    incoming=tmp_path/'Climb Studio.app.incoming';(incoming/'Contents').mkdir(parents=True);(incoming/'Contents'/'new').write_text('new')
    script=tmp_path/'install.sh';script.write_text(MAC_SWAP);opened=tmp_path/'opened'
    opener=tmp_path/'opener.sh';opener.write_text(f'#!/bin/sh\necho "$1" > "{opened}"\n');opener.chmod(0o755)
    running=subprocess.Popen(['sleep','0.6']);started=time.monotonic()
    subprocess.run(['/bin/sh',str(script),str(running.pid),str(app)],check=True,env={'PATH':'/usr/bin:/bin','CLIMB_STUDIO_OPEN':str(opener)},timeout=20,cwd=tmp_path)
    running.wait()
    assert time.monotonic()-started>=.5 and (app/'Contents'/'new').exists() and not (app/'Contents'/'old').exists()
    assert not incoming.exists() and not (tmp_path/'Climb Studio.app.previous').exists() and opened.read_text().strip()==str(app)
