"""Release interoperability tests; git history must contain v1.8.3 and v1.9.0."""
from contextlib import chdir
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / 'dev-continuity/scripts'
sys.path.insert(0, str(SCRIPTS))
import continuity as c
import test_continuity as fixtures


class VersionBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = subprocess.check_output(['git', 'show',
            '6f0a5daeb7bb473d51947f5737e07a48927103f5:dev-continuity/scripts/continuity.py'], cwd=ROOT)
        if hashlib.sha256(raw).hexdigest() != '1b694c5ce05f930601c2be65a5bc3bab73262e0a5bd1bb4889ba3e38080adb00':
            raise ValueError('unexpected v1.8.3 fixture')
        cls.old = types.ModuleType('continuity_v183')
        exec(compile(raw, 'v1.8.3/continuity.py', 'exec'), cls.old.__dict__)

    def setUp(self):
        self.f = fixtures.ContinuityTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        self.r = self.f.saved()

    def save(self, delta):
        self.r = c.save(self.root, 'task', 'old', delta, self.r, patch=True)['revision']

    def sized(self, pretty, *, reason=False):
        note = deepcopy(c.load(self.root, 'task')[0]['note'])
        if reason:
            note['memory_review']['capacity_reason'] = 'All current evidence is required.'
        note['decisions'] = ['Evidence']*1000 + ['']
        note['decisions'][-1] = 'x'*(pretty-len(c.encode(note)))
        note['memory_review']['basis_sha256'] = c.memory_basis(note)
        self.assertEqual(len(c.encode(note)), pretty)
        self.save({'decisions': note['decisions'], 'memory_review': note['memory_review']})

    def test_save_preview_promotion_and_old_mutations(self):
        self.sized(c.MAX_NOTE)
        delta = {'evidence': ['new project source'], 'next': ['continue from new project source']}
        m = c.save(self.root, 'task', 'old', delta, self.r, patch=True, dry_run=True)
        self.assertEqual(m['version'], 8)
        self.assertEqual(self.old.load(self.root,'task')[1], self.r)
        self.save(delta)
        self.assertEqual(c.recall(self.root,'task')['current']['next'], delta['next'])
        for action in ('prepare','target','release','accept','cancel'):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError,'project/task/version'):
                self.old.transfer(self.root,'task','old',self.r,action,successor='new',cancel_receipt='a.txt')
        with self.assertRaisesRegex(ValueError,'project/task/version'):
            self.old.save(self.root,'task','old',{'next':['stale']},self.r,patch=True)
        self.assertEqual(c.load(self.root,'task')[1], self.r)

    def test_80_percent_prepare_fence(self):
        self.prepare_fence(int(c.MAX_NOTE*.8)+1, reason=False)

    def test_95_percent_prepare_fence(self):
        self.prepare_fence(int(c.MAX_NOTE*.95)+1, reason=True)

    def prepare_fence(self, size, reason):
        self.sized(size, reason=reason)
        self.assertEqual(self.old.load(self.root,'task')[0]['version'],7)
        self.assertFalse(self.old.verify(self.root,'task')['new_handoff_ready'])
        q = c.transfer(self.root,'task','old',self.r,'prepare')
        with self.assertRaisesRegex(ValueError,'project/task/version'):
            self.old.transfer(self.root,'task','old',q['revision'],'target',successor='new')
        with self.assertRaisesRegex(ValueError,'reservation'):
            c.export_v7(self.root,'task','old',q['revision'])
        for action in ('target','release','accept'):
            q = c.transfer(self.root,'task','new' if action=='accept' else 'old',q['revision'],action,successor='new')
        self.assertEqual(q['handoff']['phase'],'ACCEPTED')

    def test_existing_old_reservation_remains_readable_and_frozen(self):
        q=self.old.transfer(self.root,'task','old',self.r,'prepare')
        request=q['handoff']['request_id']; settings=q['continuation_settings']
        self.f.runtime('old','low')
        for action in ('target','release','accept'):
            self.assertEqual(c.verify(self.root,'task')['capacity']['basis'],'v1.8.3')
            q=c.transfer(self.root,'task','new' if action=='accept' else 'old',q['revision'],action,successor='new')
            self.assertEqual(self.old.load(self.root,'task')[0]['version'],7)
            self.assertEqual((q['handoff']['request_id'],q['continuation_settings']),(request,settings))

    def test_export_preserves_latest_data_and_is_atomic(self):
        self.sized(c.MAX_NOTE+1)
        with self.assertRaisesRegex(ValueError,'capacity'):
            c.export_v7(self.root,'task','old',self.r)
        self.save({'decisions':['the latest decision'], 'next':['the latest pending action']})
        source=c.load(self.root,'task')[0]
        for owner,ref,why in [('old','new','stale'),('other',self.r,'owner')]:
            with self.assertRaisesRegex(ValueError,why):
                c.export_v7(self.root,'task',owner,ref)
        cli=[sys.executable,'-X','utf8','-B',str(SCRIPTS/'continuity.py'),'export-v7','--project',
             str(self.root),'--task','task','--session','old','--expected',self.r]
        preview=json.loads(subprocess.check_output(cli+['--dry-run']))
        original=c.atomic
        def fail(path,data):
            if path.name=='latest.json': raise OSError('interrupted export')
            return original(path,data)
        with patch.object(c,'atomic',side_effect=fail), self.assertRaisesRegex(OSError,'interrupted export'):
            c.export_v7(self.root,'task','old',self.r)
        self.assertEqual(c.load(self.root,'task')[1],self.r)
        result=json.loads(subprocess.check_output(cli))
        self.assertEqual(result['revision'],preview['revision'])
        v,r=self.old.load(self.root,'task')
        self.assertEqual((v['note'],v['handoff'],v['owner'],v['compat_from_revision']),
                         (source['note'],source['handoff'],source['owner'],self.r))
        self.old.save(self.root,'task','old',{'next':['continue without rewind']},r,patch=True)

    def test_v8_archive_blocks_export_even_if_note_shrinks(self):
        self.sized(c.MAX_NOTE+1)
        self.save({'decisions':[],'operations':[{'id':'used','state':'SUCCEEDED','receipt':'a.txt','retry':'never'}]})
        self.r=c.save(self.root,'task','old',{},self.r,patch=True,archive_completed=True)['revision']
        self.assertLess(len(c.encode(c.load(self.root,'task')[0]['note'])),c.MAX_NOTE)
        with self.assertRaisesRegex(ValueError,'archive requires'):
            c.export_v7(self.root,'task','old',self.r)
        self.assertTrue(c.operation(self.root,'task','used')['historical'])
        self.assertEqual(c.load(self.root,'task')[1],self.r)

    def test_changed_archived_note_source_blocks_export(self):
        path = self.root/'archived-source.txt'
        path.write_bytes(b'original')
        anchor = c.make_anchor(path, 0, 8)
        self.save({'sources':[anchor], 'operations':[{'id':'closed','state':'SUCCEEDED','receipt':'a.txt','retry':'never'}]})
        self.r=self.old.save(self.root,'task','old',{},self.r,patch=True,archive_completed=True)['revision']
        self.save({'sources':[]})
        self.sized(c.MAX_NOTE+1)
        self.save({'decisions':['latest']})
        path.write_bytes(b'replaced')
        result=c.verify(self.root,'task',history=True)
        self.assertTrue(result['ok'])
        self.assertFalse(result['history']['ok'])
        for preview in (True,False):
            with self.assertRaisesRegex(ValueError,'source'):
                c.export_v7(self.root,'task','old',self.r,preview)
            self.assertEqual(c.load(self.root,'task')[1],self.r)


    def test_v190_reads_and_updates_retained_sources_without_format_migration(self):
        raw = subprocess.check_output(['git', 'show',
            '55c7aa7d65f8edf91d4052df7dad7ec8b0fc9ab6:dev-continuity/scripts/continuity.py'], cwd=ROOT)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '35214d8fc33d4cd2600dc2a7985f7637d71fed6fa704bf5c9e8e3b4c5afd065e')
        old = types.ModuleType('continuity_v190')
        exec(compile(raw, 'v1.9.0/continuity.py', 'exec'), old.__dict__)
        self.sized(c.MAX_NOTE + 1)
        source = self.root / 'request.txt'
        anchor = {**c.make_anchor(source, 0, source.stat().st_size), 'path': source.name}
        current, _ = c.load(self.root, 'task')
        record = self.f.record('relative-boundary', current['note']['records'][0]['text'],
                               sources=[anchor], supersedes=['boundary'],
                               reason='The verified source now uses a project-relative path.')
        with chdir(self.root.parent):
            self.r = c.save(self.root, 'task', 'old', {'records': [record]}, self.r,
                            patch=True, retain_sources=True)['revision']
            source.write_bytes(b'updated current report')
            self.assertEqual(old.load(self.root, 'task'), c.load(self.root, 'task'))
            self.assertTrue(old.verify(self.root, 'task')['ok'])
            self.r = old.save(self.root, 'task', 'old', {'next': ['latest progress retained']}, self.r, patch=True)['revision']
            result, revision = c.load(self.root, 'task')
            self.assertEqual((revision, result['version'], result['note']['next']),
                             (self.r, 8, ['latest progress retained']))
            self.assertEqual(c.read_source(anchor, self.root), old.read_source(anchor, self.root))


if __name__=='__main__':
    unittest.main()
