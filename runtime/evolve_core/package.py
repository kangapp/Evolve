"""Installed package integrity; independent of project and host caches."""
import hashlib
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
    "init": ["connect", "baseline.propose", "baseline.apply"], "propose": ["create"], "update": ["revise"], "analyze": ["investigate"],
    "apply": ["implement", "external.execute", "external.reconcile", "external.record", "external.compensate"],
    "verify": ["run", "record", "knowledge"], "archive": ["close"], "sync": ["apply", "propose", "check", "review"],
    "learn": ["search", "review", "record", "retro", "promote", "disable"],
    "maintain": ["doctor", "export", "cancel", "backup", "restore", "upgrade", "recover"],
}
AVAILABLE = {"apply.external.execute", "apply.external.reconcile", "apply.external.record", "apply.external.compensate", "maintain.backup", "maintain.restore", "maintain.upgrade", "maintain.cancel", "maintain.export", "learn.promote", "sync.apply", "verify.knowledge", "sync.propose", "sync.check", "sync.review", "status.show", "maintain.doctor", "init.connect", "init.baseline.propose", "init.baseline.apply",
             "update.revise", "history.show",
             "learn.search", "learn.record", "learn.retro", "learn.review", "learn.disable", "next.show", "resume.show", "propose.create", "apply.implement", "verify.run", "archive.close", "maintain.recover", "analyze.investigate"}
ROOT = Path(__file__).resolve().parents[2]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


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
        required = {"README.md", "LICENSE", "NOTICE.md", "CHANGELOG.md",
                    "docs/installation.md", "docs/usage.md", "docs/troubleshooting.md", "docs/development.md", "docs/compatibility.md", "docs/project-layout.md",
                    ".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json", "shared/contract.md", "shared/learning-cycle.md", "shared/recovery.md", "shared/external-work.md",
                    "runtime/evolve.py", "runtime/evolve_core/cli.py", "assets/templates/config.toml",
                    ".codex-plugin/plugin.json", ".claude-plugin/plugin.json"}
        required.update(f"skills/evolve-{owner}/SKILL.md" for owner in set(OWNERS.values()))
        required.update('runtime/evolve_core/' + name + '.py' for name in (
            '__init__', 'errors', 'package', 'cli', 'reading', 'requests', 'privacy', 'store', 'workspace',
            'backup', 'archive_sets', 'protection', 'maintenance', 'external_material', 'external', 'external_registry', 'external_process', 'external_recovery', 'external_actions', 'external_work', 'plans', 'structured', 'preservation', 'revisions', 'connect', 'configure', 'config_edit', 'work', 'checks', 'apply', 'verify', 'archive', 'recover', 'knowledge', 'knowledge_proposals', 'formal', 'patches', 'analysis', 'data_material', 'exporting', 'cancellation', 'cross_dependencies', 'continuation', 'resume', 'learning', 'rules'))
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
