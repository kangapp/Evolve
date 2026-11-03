"""Installed package integrity; independent of project and host caches."""
import hashlib
import ast
import json
from pathlib import Path, PurePosixPath
from . import VERSION, PROTOCOL_VERSION, SCHEMA_VERSION, DESIGN_BASELINE
from .errors import EvolveError

OWNERS = {
    "status": "workflow", "next": "workflow", "resume": "workflow",
    "init": "init", "propose": "propose", "update": "propose", "analyze": "propose",
    "apply": "apply", "verify": "verify", "archive": "archive", "sync": "archive",
    "learn": "learn", "history": "maintain", "maintain": "maintain",
}
METHODS = {
    "status": ["show"], "next": ["show"], "resume": ["show"], "history": ["show"],
    "init": ["connect", "baseline.propose", "baseline.apply", "templates", "survey", "complete"], "propose": ["create"], "update": ["revise"], "analyze": ["investigate"],
    "apply": ["implement", "external.execute", "external.reconcile", "external.record", "external.compensate"],
    "verify": ["run", "record", "knowledge"], "archive": ["close"], "sync": ["apply", "propose", "check", "review", "facts", "assess"],
    "learn": ["search", "review", "record", "retro", "promote", "disable"],
    "maintain": ["doctor", "export", "cancel", "backup", "restore", "upgrade", "recover", "repair", "materials", "clean"],
}
AVAILABLE = {"apply.external.execute", "apply.external.reconcile", "apply.external.record", "apply.external.compensate", "maintain.backup", "maintain.restore", "maintain.upgrade", "maintain.cancel", "maintain.export", "learn.promote", "sync.apply", "verify.knowledge", "sync.propose", "sync.check", "sync.review", "status.show", "maintain.doctor", "init.connect", "init.baseline.propose", "init.baseline.apply",
             "update.revise", "history.show",
             "learn.search", "learn.record", "learn.retro", "learn.review", "learn.disable", "next.show", "resume.show", "propose.create", "apply.implement", "verify.run", "archive.close", "maintain.recover", "analyze.investigate"}
AVAILABLE.update({'init.templates', 'init.survey', 'init.complete', 'sync.facts', 'sync.assess'})
AVAILABLE.update({'maintain.repair', 'maintain.materials', 'maintain.clean'})
UPGRADE_PROTOCOLS = ('14', '15', '16', '17')
ENGINEERING_MODULES = ('check_environment', 'planning_impacts', 'workflow_requests', 'change_views', 'check_reuse', 'review_materials')
ROOT = Path(__file__).resolve().parents[2]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def check_provenance(manifest):
    if manifest.get('protocol_version', 0) < 18:
        return
    observation = manifest.get('source_observation')
    if (not isinstance(observation, dict) or observation.get('kind') != 'build_time_observation'
            or not isinstance(observation.get('source_root'), str)
            or not isinstance(observation.get('source_content_digest'), str)
            or len(observation['source_content_digest']) != 64
            or observation.get('source_attestation') != 'unsigned'
            or observation.get('git_dirty') is not None and type(observation['git_dirty']) is not bool
            or manifest.get('source_observation_digest') != digest(canonical(observation))):
        raise EvolveError('PACKAGE_INCOMPLETE', 'Build source observation is missing or changed')


def file_at(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts or "\\" in name or not rel.parts:
        raise EvolveError("PACKAGE_PATH", "Invalid package path: " + name)
    path = root.joinpath(*rel.parts)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise EvolveError("PACKAGE_PATH", "Package reference escapes its root: " + name)
    if path.is_symlink():
        raise EvolveError("PACKAGE_PATH", "Package files must not be symbolic links: " + name)
    return path


def inspect_package(root):
    """Inspect another complete release without importing or executing its code."""
    root = Path(root).resolve()
    try:
        manifest = json.loads((root / 'evolve-package.json').read_text())
        files = manifest['files']
        check_provenance(manifest)
        required = required_resources(workflow=manifest.get('package_version') != '0.2.0',
                                      engineering=manifest.get('protocol_version', 0) >= 18)
        if not isinstance(files, dict) or not required.issubset(files) or manifest['content_digest'] != digest(canonical(files)):
            raise ValueError('Incomplete release inventory')
        for name, value in files.items():
            path = file_at(root, name)
            if not path.is_file() or digest(path.read_bytes()) != value:
                raise ValueError('Missing or modified resource: ' + name)
        for host in ('codex', 'claude'):
            plugin = json.loads((root / ('.' + host + '-plugin/plugin.json')).read_text())
            if plugin['version'] != manifest['package_version'] or plugin['name'] != 'evolve':
                raise ValueError('Host manifest differs from release')
        definitions = {}
        for node in ast.parse((root / 'runtime/evolve_core/__init__.py').read_text()).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                definitions[node.targets[0].id] = ast.literal_eval(node.value)
        if any(definitions.get(symbol) != manifest.get(field) for symbol, field in (
                ('VERSION', 'package_version'), ('PROTOCOL_VERSION', 'protocol_version'), ('SCHEMA_VERSION', 'schema_version'))):
            raise ValueError('Candidate runtime declarations differ from release inventory')
        return manifest
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        raise EvolveError('PACKAGE_INCOMPLETE', 'Cannot verify candidate package: ' + str(error)) from error



def required_resources(*, workflow=True, engineering=True):
    required = {"README.md", "LICENSE", "NOTICE.md", "CHANGELOG.md",
                "docs/installation.md", "docs/usage.md", "docs/troubleshooting.md", "docs/development.md", "docs/compatibility.md", "docs/project-layout.md", "docs/workflows.md", "docs/architecture.md",
                ".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json", "shared/contract.md", "shared/learning-cycle.md", "shared/recovery.md", "shared/external-work.md", "shared/workflow-experience.md", "shared/plugin-update.md",
                "runtime/evolve.py", "runtime/evolve_core/cli.py", "assets/templates/config.toml",
                ".codex-plugin/plugin.json", ".claude-plugin/plugin.json"}
    required.update(f"skills/evolve-{owner}/SKILL.md" for owner in set(OWNERS.values()))
    from .project_knowledge import KINDS
    required.update('assets/templates/knowledge-' + kind + '.md' for kind in KINDS)
    required.update('runtime/evolve_core/' + name + '.py' for name in (
        '__init__', 'errors', 'package', 'cli', 'reading', 'requests', 'privacy', 'store', 'workspace', 'project_knowledge', 'knowledge_facts', 'knowledge_impact', 'guidance',
        'backup', 'archive_sets', 'protection', 'maintenance', 'external_material', 'external', 'external_registry', 'external_process', 'external_recovery', 'external_actions', 'external_work', 'plans', 'structured', 'preservation', 'revisions', 'connect', 'configure', 'config_edit', 'work', 'checks', 'apply', 'verify', 'archive', 'recover', 'knowledge', 'knowledge_proposals', 'formal', 'patches', 'analysis', 'data_material', 'exporting', 'cancellation', 'cross_dependencies', 'continuation', 'resume', 'learning', 'rules'))
    if not workflow:
        required.difference_update({"shared/workflow-experience.md", "shared/plugin-update.md", "runtime/evolve_core/guidance.py"})
    if engineering:
        required.update('runtime/evolve_core/' + name + '.py' for name in ENGINEERING_MODULES)
    return required

def check_package(root=ROOT):
    root = Path(root)
    try:
        manifest = json.loads((root / "evolve-package.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), dict):
            raise EvolveError('PACKAGE_INCOMPLETE', 'Package inventory must be an object with a file digest map')
        expected = {"package_version": VERSION, "protocol_version": PROTOCOL_VERSION,
                    "schema_version": SCHEMA_VERSION, "design_baseline": DESIGN_BASELINE}
        for key, value in expected.items():
            if manifest.get(key) != value:
                raise EvolveError("PACKAGE_VERSION", f"Package {key} does not match runtime")
        files = manifest["files"]
        check_provenance(manifest)
        required = required_resources()
        if not required.issubset(files):
            raise EvolveError("PACKAGE_INCOMPLETE", "Missing required package inventory entries")
        for name, expected_hash in files.items():
            path = file_at(root, name)
            if not path.is_file() or digest(path.read_bytes()) != expected_hash:
                raise EvolveError("PACKAGE_INCOMPLETE", "Missing or modified package resource: " + name,
                                  next_steps=["Rebuild or reinstall the complete same-version package"])
        if manifest["content_digest"] != digest(canonical(files)):
            raise EvolveError("PACKAGE_INCOMPLETE", "Package inventory digest does not match")
        for host in ("codex", "claude"):
            data = json.loads((root / f".{host}-plugin/plugin.json").read_text(encoding="utf-8"))
            if data.get("version") != VERSION or data.get("name") != "evolve":
                raise EvolveError("PACKAGE_VERSION", "Host manifest and runtime differ")
        if manifest.get("available_methods") != sorted(AVAILABLE):
            raise EvolveError("PACKAGE_VERSION", "Advertised methods do not match runtime")
        return manifest
    except EvolveError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise EvolveError("PACKAGE_INCOMPLETE", "Cannot inspect complete package: " + str(error),
                          next_steps=["Install a complete Evolve package; do not copy individual skills"])
