from __future__ import annotations

from math_im_book.domain.models import KnowledgeNode, SymbolContext


class SymbolRegistry:
    def build_context(
        self,
        nodes: list[KnowledgeNode],
        branch_symbols: dict[str, str] | None = None,
        include_local_symbols: bool = False,
    ) -> SymbolContext:
        global_symbols, global_conflicts = self._collect_global_symbols(nodes)
        local_symbols, local_conflicts = self._collect_local_symbols(nodes)
        symbols = dict(global_symbols)
        conflicts = [*global_conflicts]
        symbols.update(branch_symbols or {})
        if include_local_symbols:
            conflicts.extend(local_conflicts)
            symbols.update(local_symbols)
        return SymbolContext(symbols=symbols, conflicts=conflicts)

    @staticmethod
    def _collect_global_symbols(
        nodes: list[KnowledgeNode],
    ) -> tuple[dict[str, str], list[str]]:
        scope_symbols: dict[str, str] = {}
        conflicts: list[str] = []
        for node in nodes:
            for symbol, meaning in sorted(node.symbols.items()):
                if symbol in scope_symbols and scope_symbols[symbol] != meaning:
                    conflicts.append(
                        f"Symbol {symbol} has conflicting meanings: '{scope_symbols[symbol]}' vs '{meaning}'."
                    )
                    continue
                scope_symbols.setdefault(symbol, meaning)
            for symbol, meaning in sorted(node.symbol_scopes.get("global", {}).items()):
                if symbol in scope_symbols and scope_symbols[symbol] != meaning:
                    conflicts.append(
                        f"Symbol {symbol} has conflicting meanings: '{scope_symbols[symbol]}' vs '{meaning}'."
                    )
                    continue
                scope_symbols.setdefault(symbol, meaning)
        return scope_symbols, conflicts

    @staticmethod
    def _collect_local_symbols(
        nodes: list[KnowledgeNode],
    ) -> tuple[dict[str, str], list[str]]:
        scope_symbols: dict[str, str] = {}
        conflicts: list[str] = []
        for node in nodes:
            for symbol, meaning in sorted(node.symbol_scopes.get("local", {}).items()):
                if symbol in scope_symbols and scope_symbols[symbol] != meaning:
                    conflicts.append(
                        f"Symbol {symbol} has conflicting meanings: '{scope_symbols[symbol]}' vs '{meaning}'."
                    )
                    continue
                scope_symbols[symbol] = meaning
        return scope_symbols, conflicts
