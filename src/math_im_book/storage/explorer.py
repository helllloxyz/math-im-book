from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

VALID_SCOPES = {"sessions", "knowledge"}
ITEM_SCOPE = {"session": "sessions", "knowledge_node": "knowledge"}
VALID_LOCATION_SOURCES = {"user", "agent", "system"}


class ExplorerError(ValueError):
    pass


class ExplorerFolderConflictError(ExplorerError):
    pass


class ExplorerInvalidMoveError(ExplorerError):
    pass


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_folder_id() -> str:
    return f"folder-{uuid4().hex[:12]}"


def _new_scope_id() -> str:
    return f"scope-{uuid4().hex[:12]}"


def _folder_path(name_parts: list[str]) -> str:
    return "/" + "/".join(name_parts) if name_parts else "/"


@dataclass(slots=True)
class ExplorerFolder:
    folder_id: str
    scope: str
    name: str
    parent_folder_id: str | None
    created_at: str
    updated_at: str
    sort_order: int = 1000
    path_cached: str = field(default="/")
    scope_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "folder_id": self.folder_id,
            "scope": self.scope,
            "name": self.name,
            "parent_folder_id": self.parent_folder_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sort_order": self.sort_order,
            "path_cached": self.path_cached,
            "scope_id": self.scope_id,
        }


@dataclass(slots=True)
class ExplorerItemLocation:
    item_type: str
    item_id: str
    folder_id: str | None
    sort_order: int
    path_cached: str
    location_source: str
    user_locked: bool
    updated_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_type": self.item_type,
            "item_id": self.item_id,
            "folder_id": self.folder_id,
            "sort_order": self.sort_order,
            "path_cached": self.path_cached,
            "location_source": self.location_source,
            "user_locked": self.user_locked,
            "updated_at": self.updated_at,
        }


class ExplorerStore:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def load_payload(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"version": 1, "folders": [], "locations": [], "item_icons": []}
        with self.index_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload.setdefault("version", 1)
        payload.setdefault("folders", [])
        payload.setdefault("locations", [])
        payload.setdefault("item_icons", [])
        return payload

    def create_folder(
        self,
        *,
        scope: str,
        name: str,
        parent_folder_id: str | None,
        sort_order: int = 1000,
        scope_id: str | None = None,
    ) -> ExplorerFolder:
        scope = self._validate_scope(scope)
        name = self._validate_folder_name(name)
        payload = self.load_payload()
        folders = payload["folders"]
        parent = self._get_folder(folders, parent_folder_id) if parent_folder_id else None
        if parent_folder_id is not None and parent is None:
            raise KeyError(parent_folder_id)
        if parent is not None and parent["scope"] != scope:
            raise ExplorerInvalidMoveError("parent folder scope mismatch")
        if parent is not None:
            scope_id = parent.get("scope_id")
        self._raise_on_duplicate_sibling_name(
            folders,
            scope=scope,
            name=name,
            parent_folder_id=parent_folder_id,
        )

        now = _utcnow()
        folder = ExplorerFolder(
            folder_id=_new_folder_id(),
            scope=scope,
            name=name,
            parent_folder_id=parent_folder_id,
            created_at=now,
            updated_at=now,
            sort_order=sort_order,
            path_cached="/",
            scope_id=scope_id,
        )
        folders.append(self._folder_to_dict(folder))
        self._refresh_cached_paths(payload)
        self._save_payload(payload)
        return self._folder_from_dict(self._get_folder(payload["folders"], folder.folder_id))

    def create_scope_root(
        self,
        *,
        name: str,
        primary_scope: str,
        sort_order: int = 1000,
    ) -> tuple[ExplorerFolder, ExplorerFolder]:
        """Create the conversation and Library roots for one user scope."""
        primary_scope = self._validate_scope(primary_scope)
        name = self._validate_folder_name(name)
        paired_scope = "knowledge" if primary_scope == "sessions" else "sessions"
        payload = self.load_payload()
        folders = payload["folders"]
        self._raise_on_duplicate_sibling_name(
            folders,
            scope=primary_scope,
            name=name,
            parent_folder_id=None,
        )
        self._raise_on_duplicate_sibling_name(
            folders,
            scope=paired_scope,
            name=name,
            parent_folder_id=None,
        )

        now = _utcnow()
        scope_id = _new_scope_id()
        created: dict[str, str] = {}
        for scope in (primary_scope, paired_scope):
            folder = ExplorerFolder(
                folder_id=_new_folder_id(),
                scope=scope,
                name=name,
                parent_folder_id=None,
                created_at=now,
                updated_at=now,
                sort_order=sort_order,
                path_cached="/",
                scope_id=scope_id,
            )
            folders.append(self._folder_to_dict(folder))
            created[scope] = folder.folder_id
        self._refresh_cached_paths(payload)
        self._save_payload(payload)
        primary = self._folder_from_dict(
            self._get_folder(payload["folders"], created[primary_scope])
        )
        paired = self._folder_from_dict(
            self._get_folder(payload["folders"], created[paired_scope])
        )
        return primary, paired

    def ensure_scope_root_pair(self, folder_id: str) -> tuple[ExplorerFolder, ExplorerFolder]:
        """Return a folder's scope root and its paired root, migrating legacy roots."""
        payload = self.load_payload()
        folders = payload["folders"]
        folder = self._get_folder(folders, folder_id)
        if folder is None:
            raise KeyError(folder_id)
        root = self._root_folder_dict(folders, folder)
        scope_id = root.get("scope_id") or _new_scope_id()
        changed = root.get("scope_id") != scope_id
        root["scope_id"] = scope_id

        paired_scope = "knowledge" if root["scope"] == "sessions" else "sessions"
        paired = next(
            (
                candidate
                for candidate in folders
                if candidate["scope"] == paired_scope
                and candidate["parent_folder_id"] is None
                and candidate.get("scope_id") == scope_id
            ),
            None,
        )
        if paired is None:
            paired = next(
                (
                    candidate
                    for candidate in folders
                    if candidate["scope"] == paired_scope
                    and candidate["parent_folder_id"] is None
                    and candidate["name"] == root["name"]
                    and not candidate.get("scope_id")
                ),
                None,
            )
        if paired is None:
            self._raise_on_duplicate_sibling_name(
                folders,
                scope=paired_scope,
                name=root["name"],
                parent_folder_id=None,
            )
            now = _utcnow()
            paired_folder = ExplorerFolder(
                folder_id=_new_folder_id(),
                scope=paired_scope,
                name=root["name"],
                parent_folder_id=None,
                created_at=now,
                updated_at=now,
                sort_order=root.get("sort_order", 1000),
                path_cached="/",
                scope_id=scope_id,
            )
            paired = self._folder_to_dict(paired_folder)
            folders.append(paired)
            changed = True
        elif paired.get("scope_id") != scope_id:
            paired["scope_id"] = scope_id
            changed = True

        paired_root_ids = {root["folder_id"], paired["folder_id"]}
        for candidate in folders:
            candidate_root = self._root_folder_dict(folders, candidate)
            if candidate_root["folder_id"] not in paired_root_ids:
                continue
            if candidate.get("scope_id") != scope_id:
                candidate["scope_id"] = scope_id
                changed = True

        if changed:
            self._refresh_cached_paths(payload)
            self._save_payload(payload)
        return self._folder_from_dict(root), self._folder_from_dict(paired)

    def paired_scope_root(self, folder_id: str, *, target_scope: str) -> ExplorerFolder:
        target_scope = self._validate_scope(target_scope)
        first, second = self.ensure_scope_root_pair(folder_id)
        return first if first.scope == target_scope else second

    def root_folder(self, folder_id: str) -> ExplorerFolder:
        payload = self.load_payload()
        folder = self._get_folder(payload["folders"], folder_id)
        if folder is None:
            raise KeyError(folder_id)
        return self._folder_from_dict(
            self._root_folder_dict(payload["folders"], folder)
        )

    def rename_scope_root(self, folder_id: str, name: str) -> ExplorerFolder:
        name = self._validate_folder_name(name)
        root, paired = self.ensure_scope_root_pair(folder_id)
        if root.folder_id != folder_id:
            return self.rename_folder(folder_id, name)
        payload = self.load_payload()
        folders = payload["folders"]
        for candidate in (root, paired):
            self._raise_on_duplicate_sibling_name(
                folders,
                scope=candidate.scope,
                name=name,
                parent_folder_id=None,
                exclude_folder_id=candidate.folder_id,
            )
        now = _utcnow()
        for candidate_id in (root.folder_id, paired.folder_id):
            candidate = self._get_folder(folders, candidate_id)
            if candidate is not None:
                candidate["name"] = name
                candidate["updated_at"] = now
        self._refresh_cached_paths(payload)
        self._save_payload(payload)
        renamed = self._get_folder(payload["folders"], folder_id)
        return self._folder_from_dict(renamed)

    def delete_scope_root(self, folder_id: str) -> None:
        root, paired = self.ensure_scope_root_pair(folder_id)
        if root.folder_id != folder_id:
            self.delete_folder(folder_id)
            return
        payload = self.load_payload()
        target_ids = {root.folder_id, paired.folder_id}
        if any(
            folder["parent_folder_id"] in target_ids
            for folder in payload["folders"]
        ):
            raise ExplorerInvalidMoveError("folder contains child folders")
        if any(
            location["folder_id"] in target_ids
            for location in payload["locations"]
        ):
            raise ExplorerInvalidMoveError("folder contains item locations")
        payload["folders"] = [
            folder
            for folder in payload["folders"]
            if folder["folder_id"] not in target_ids
        ]
        self._refresh_cached_paths(payload)
        self._save_payload(payload)

    def rename_folder(self, folder_id: str, name: str) -> ExplorerFolder:
        name = self._validate_folder_name(name)
        payload = self.load_payload()
        folder = self._get_folder(payload["folders"], folder_id)
        if folder is None:
            raise KeyError(folder_id)
        self._raise_on_duplicate_sibling_name(
            payload["folders"],
            scope=folder["scope"],
            name=name,
            parent_folder_id=folder["parent_folder_id"],
            exclude_folder_id=folder_id,
        )
        folder["name"] = name
        folder["updated_at"] = _utcnow()
        self._refresh_cached_paths(payload)
        self._save_payload(payload)
        return self._folder_from_dict(folder)

    def delete_folder(self, folder_id: str) -> None:
        payload = self.load_payload()
        folder = self._get_folder(payload["folders"], folder_id)
        if folder is None:
            raise KeyError(folder_id)
        if any(item["parent_folder_id"] == folder_id for item in payload["folders"]):
            raise ExplorerInvalidMoveError("folder contains child folders")
        if any(location["folder_id"] == folder_id for location in payload["locations"]):
            raise ExplorerInvalidMoveError("folder contains item locations")
        payload["folders"] = [item for item in payload["folders"] if item["folder_id"] != folder_id]
        self._refresh_cached_paths(payload)
        self._save_payload(payload)

    def move_item(
        self,
        *,
        item_type: str,
        item_id: str,
        folder_id: str | None,
        sort_order: int,
        location_source: str,
    ) -> ExplorerItemLocation:
        item_type = self._validate_item_type(item_type)
        scope = ITEM_SCOPE[item_type]
        location_source = self._validate_location_source(location_source)
        payload = self.load_payload()
        folder = None
        if folder_id is not None:
            folder = self._get_folder(payload["folders"], folder_id)
            if folder is None:
                raise ExplorerInvalidMoveError("Target folder does not exist")
            if folder["scope"] != scope:
                raise ExplorerInvalidMoveError("Target folder is not in the item scope")

        now = _utcnow()
        location = ExplorerItemLocation(
            item_type=item_type,
            item_id=item_id,
            folder_id=folder_id,
            sort_order=sort_order,
            path_cached=self._build_item_path(payload["folders"], folder_id, item_id),
            location_source=location_source,
            user_locked=(location_source == "user"),
            updated_at=now,
        )
        payload["locations"] = [
            item for item in payload["locations"] if not self._same_item_location(item, item_type, item_id)
        ]
        payload["locations"].append(self._location_to_dict(location))
        self._save_payload(payload)
        return location

    def ensure_item_location(
        self,
        *,
        item_type: str,
        item_id: str,
        folder_id: str | None = None,
        location_source: str = "system",
        sort_order: int = 1000,
    ) -> ExplorerItemLocation:
        existing = self.find_location(item_type, item_id)
        if existing is not None:
            return existing
        return self.move_item(
            item_type=item_type,
            item_id=item_id,
            folder_id=folder_id,
            sort_order=sort_order,
            location_source=location_source,
        )

    def find_location(self, item_type: str, item_id: str) -> ExplorerItemLocation | None:
        payload = self.load_payload()
        location = self._find_location_dict(payload["locations"], item_type, item_id)
        if location is None:
            return None
        return self._location_from_dict(location)

    def find_folder(
        self,
        *,
        scope: str,
        name: str,
        parent_folder_id: str | None = None,
    ) -> ExplorerFolder | None:
        scope = self._validate_scope(scope)
        name = self._validate_folder_name(name)
        payload = self.load_payload()
        for folder in payload["folders"]:
            if (
                folder["scope"] == scope
                and folder["name"] == name
                and folder["parent_folder_id"] == parent_folder_id
            ):
                return self._folder_from_dict(folder)
        return None

    def get_folder(self, folder_id: str) -> ExplorerFolder:
        payload = self.load_payload()
        folder = self._get_folder(payload["folders"], folder_id)
        if folder is None:
            raise KeyError(folder_id)
        return self._folder_from_dict(folder)

    def list_folders(self, scope: str) -> list[ExplorerFolder]:
        scope = self._validate_scope(scope)
        payload = self.load_payload()
        folders = [
            self._folder_from_dict(folder)
            for folder in payload["folders"]
            if folder["scope"] == scope
        ]
        return sorted(folders, key=lambda folder: (folder.path_cached, folder.folder_id))

    def list_item_ids_in_folder(
        self,
        *,
        item_type: str,
        folder_id: str,
        include_descendants: bool = True,
    ) -> list[str]:
        item_type = self._validate_item_type(item_type)
        payload = self.load_payload()
        folder = self._get_folder(payload["folders"], folder_id)
        if folder is None:
            raise KeyError(folder_id)
        if folder["scope"] != ITEM_SCOPE[item_type]:
            raise ExplorerInvalidMoveError("folder scope does not match item type")

        folder_ids = {folder_id}
        if include_descendants:
            pending = [folder_id]
            while pending:
                parent_id = pending.pop()
                child_ids = [
                    candidate["folder_id"]
                    for candidate in payload["folders"]
                    if candidate["parent_folder_id"] == parent_id
                ]
                for child_id in child_ids:
                    if child_id in folder_ids:
                        continue
                    folder_ids.add(child_id)
                    pending.append(child_id)

        return sorted(
            {
                location["item_id"]
                for location in payload["locations"]
                if location["item_type"] == item_type
                and location["folder_id"] in folder_ids
            }
        )

    def remove_item(self, *, item_type: str, item_id: str) -> bool:
        """Remove Explorer-only metadata after the source item is deleted.

        The Explorer does not own conversations or knowledge files, but stale
        locations can otherwise keep an empty folder from being deleted.
        """
        item_type = self._validate_item_type(item_type)
        payload = self.load_payload()
        original_location_count = len(payload["locations"])
        original_icon_count = len(payload["item_icons"])
        payload["locations"] = [
            item
            for item in payload["locations"]
            if not self._same_item_location(item, item_type, item_id)
        ]
        payload["item_icons"] = [
            item
            for item in payload["item_icons"]
            if not self._same_item_location(item, item_type, item_id)
        ]
        removed = (
            len(payload["locations"]) != original_location_count
            or len(payload["item_icons"]) != original_icon_count
        )
        if removed:
            self._save_payload(payload)
        return removed

    def set_item_icon(self, *, item_type: str, item_id: str, icon: str) -> dict[str, Any]:
        item_type = self._validate_item_type(item_type)
        icon = self._validate_icon(icon)
        payload = self.load_payload()
        now = _utcnow()
        item_icon = {
            "item_type": item_type,
            "item_id": item_id,
            "icon": icon,
            "updated_at": now,
        }
        payload["item_icons"] = [
            item for item in payload["item_icons"] if not self._same_item_location(item, item_type, item_id)
        ]
        payload["item_icons"].append(item_icon)
        self._save_payload(payload)
        return item_icon

    def build_tree(
        self,
        *,
        scope: str,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        scope = self._validate_scope(scope)
        payload = self.load_payload()
        folders = [folder for folder in payload["folders"] if folder["scope"] == scope]
        folder_ids = {folder["folder_id"] for folder in folders}
        locations = {
            (location["item_type"], location["item_id"]): location
            for location in payload["locations"]
            if ITEM_SCOPE.get(location["item_type"]) == scope
        }
        item_icons = {
            (item_icon["item_type"], item_icon["item_id"]): item_icon["icon"]
            for item_icon in payload["item_icons"]
            if ITEM_SCOPE.get(item_icon["item_type"]) == scope
        }
        items_by_folder: dict[str | None, list[dict[str, Any]]] = {}
        for item in items:
            item_type = self._validate_item_type(item["item_type"])
            if ITEM_SCOPE[item_type] != scope:
                continue
            location = locations.get((item_type, item["item_id"]))
            normalized_location = (
                self._location_from_dict(location).as_dict()
                if location is not None
                else self._synthesized_location(item_type, item["item_id"], sort_order=1000)
            )
            if location is not None and location["folder_id"] not in folder_ids:
                normalized_location["folder_id"] = None
                normalized_location["path_cached"] = f"/{item['item_id']}"
            folder_id = normalized_location["folder_id"]
            tree_item = dict(item)
            tree_item["item_type"] = item_type
            tree_item["item_id"] = item["item_id"]
            tree_item.setdefault("title", item["item_id"])
            icon = item_icons.get((item_type, item["item_id"]))
            if icon is not None:
                tree_item["icon"] = icon
            items_by_folder.setdefault(folder_id, []).append(
                {
                    "kind": "item",
                    "item": tree_item,
                    "location": normalized_location,
                }
            )

        def build_children(parent_folder_id: str | None) -> list[dict[str, Any]]:
            nodes: list[dict[str, Any]] = []
            for folder in sorted(
                [folder for folder in folders if folder["parent_folder_id"] == parent_folder_id],
                key=lambda item: (item["sort_order"], item["name"]),
            ):
                nodes.append(
                    {
                        "kind": "folder",
                        "folder": self._folder_from_dict(folder).as_dict(),
                        "children": build_children(folder["folder_id"]),
                    }
                )
            for item in sorted(
                items_by_folder.get(parent_folder_id, []),
                key=lambda item: (item["location"]["sort_order"], item["item"]["title"]),
            ):
                nodes.append(item)
            return nodes

        return build_children(None)

    def _save_payload(self, payload: dict[str, Any]) -> None:
        with self.index_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))

    def _validate_scope(self, scope: str) -> str:
        if scope not in VALID_SCOPES:
            raise ExplorerError(f"invalid scope: {scope}")
        return scope

    def _validate_item_type(self, item_type: str) -> str:
        if item_type not in ITEM_SCOPE:
            raise ExplorerError(f"invalid item type: {item_type}")
        return item_type

    def _validate_location_source(self, location_source: str) -> str:
        if location_source not in VALID_LOCATION_SOURCES:
            raise ExplorerError(f"invalid location source: {location_source}")
        return location_source

    def _validate_folder_name(self, name: str) -> str:
        if not name or not name.strip():
            raise ExplorerError("folder name must not be empty")
        return name.strip()

    def _validate_icon(self, icon: str) -> str:
        if not icon or not icon.strip():
            raise ExplorerError("icon must not be empty")
        return icon.strip()

    def _get_folder(self, folders: list[dict[str, Any]], folder_id: str | None) -> dict[str, Any] | None:
        if folder_id is None:
            return None
        for folder in folders:
            if folder["folder_id"] == folder_id:
                return folder
        return None

    def _root_folder_dict(
        self,
        folders: list[dict[str, Any]],
        folder: dict[str, Any],
    ) -> dict[str, Any]:
        current = folder
        visited = {current["folder_id"]}
        while current["parent_folder_id"] is not None:
            parent = self._get_folder(folders, current["parent_folder_id"])
            if parent is None:
                raise ExplorerInvalidMoveError("folder references missing parent")
            if parent["folder_id"] in visited:
                raise ExplorerInvalidMoveError("folder hierarchy contains a cycle")
            visited.add(parent["folder_id"])
            current = parent
        return current

    def _raise_on_duplicate_sibling_name(
        self,
        folders: list[dict[str, Any]],
        *,
        scope: str,
        name: str,
        parent_folder_id: str | None,
        exclude_folder_id: str | None = None,
    ) -> None:
        for folder in folders:
            if folder["scope"] != scope:
                continue
            if folder["parent_folder_id"] != parent_folder_id:
                continue
            if folder["folder_id"] == exclude_folder_id:
                continue
            if folder["name"] == name:
                raise ExplorerFolderConflictError("duplicate sibling folder name")

    def _refresh_cached_paths(self, payload: dict[str, Any]) -> None:
        folders = payload["folders"]
        folder_map = {folder["folder_id"]: folder for folder in folders}

        def folder_name_parts(folder: dict[str, Any]) -> list[str]:
            parts: list[str] = [folder["name"]]
            parent_id = folder["parent_folder_id"]
            while parent_id is not None:
                parent = folder_map[parent_id]
                parts.append(parent["name"])
                parent_id = parent["parent_folder_id"]
            return list(reversed(parts))

        for folder in folders:
            folder["path_cached"] = _folder_path(folder_name_parts(folder))
        for location in payload["locations"]:
            folder_id = location["folder_id"]
            if folder_id is None:
                location["path_cached"] = f"/{location['item_id']}"
                continue
            folder = folder_map.get(folder_id)
            if folder is None:
                raise ExplorerInvalidMoveError("location references missing folder")
            location["path_cached"] = f"{folder['path_cached']}/{location['item_id']}"

    def _build_item_path(self, folders: list[dict[str, Any]], folder_id: str | None, item_id: str) -> str:
        if folder_id is None:
            return f"/{item_id}"
        folder = self._get_folder(folders, folder_id)
        if folder is None:
            raise ExplorerInvalidMoveError("target folder does not exist")
        return f"{folder['path_cached']}/{item_id}"

    def _find_location_dict(
        self,
        locations: list[dict[str, Any]],
        item_type: str,
        item_id: str,
    ) -> dict[str, Any] | None:
        for location in locations:
            if location["item_type"] == item_type and location["item_id"] == item_id:
                return location
        return None

    def _same_item_location(self, location: dict[str, Any], item_type: str, item_id: str) -> bool:
        return location["item_type"] == item_type and location["item_id"] == item_id

    def _folder_to_dict(self, folder: ExplorerFolder) -> dict[str, Any]:
        return folder.as_dict()

    def _folder_from_dict(self, folder: dict[str, Any]) -> ExplorerFolder:
        return ExplorerFolder(
            folder_id=folder["folder_id"],
            scope=folder["scope"],
            name=folder["name"],
            parent_folder_id=folder["parent_folder_id"],
            created_at=folder["created_at"],
            updated_at=folder["updated_at"],
            sort_order=folder.get("sort_order", 1000),
            path_cached=folder.get("path_cached", "/"),
            scope_id=folder.get("scope_id"),
        )

    def _location_to_dict(self, location: ExplorerItemLocation) -> dict[str, Any]:
        return location.as_dict()

    def _location_from_dict(self, location: dict[str, Any]) -> ExplorerItemLocation:
        return ExplorerItemLocation(
            item_type=location["item_type"],
            item_id=location["item_id"],
            folder_id=location["folder_id"],
            sort_order=location["sort_order"],
            path_cached=location["path_cached"],
            location_source=location["location_source"],
            user_locked=location["user_locked"],
            updated_at=location["updated_at"],
        )

    def _synthesized_location(
        self,
        item_type: str,
        item_id: str,
        *,
        sort_order: int,
    ) -> dict[str, Any]:
        return {
            "item_type": item_type,
            "item_id": item_id,
            "folder_id": None,
            "sort_order": sort_order,
            "path_cached": f"/{item_id}",
            "location_source": "system",
            "user_locked": False,
            "updated_at": _utcnow(),
        }
