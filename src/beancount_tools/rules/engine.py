"""
Rule Engine for Tree Rules v2 Specification

Implements the tree-based rule matching and action execution system.
Uses MongoDB-inspired syntax with $-prefixed operators.

Key differences from v1:
- ``match:`` replaces ``when:``
- ``apply:`` replaces ``then:``
- Logical operators use $ prefix: $any, $all, $not
- Plain string = exact match; /pattern/ = regex search
- Set fields use "contains" semantics
- Actions use $add/$remove instead of +/- prefix magic
"""

import re
from typing import Any, Dict, List, Optional, Union

import yaml


class RuleEngine:
    """Engine for parsing and applying tree-based rules to transactions."""

    # Operator keys recognized inside a match expression
    _OPERATORS = {"$all", "$any", "$not"}

    def __init__(self, rules_data: Union[str, dict]):
        """
        Initialize the rule engine.

        Args:
            rules_data: Either a YAML string or a parsed dict containing rules
        """
        if isinstance(rules_data, str):
            self.rules = yaml.safe_load(rules_data)
        else:
            self.rules = rules_data

        if not isinstance(self.rules, dict) or "rules" not in self.rules:
            raise ValueError(
                "Rules must contain a 'rules' key with a list of rule nodes"
            )

    def match_and_apply(
        self, tx_dict: Dict[str, Any], parent_match: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Apply rules to a transaction dictionary.

        Args:
            tx_dict: Transaction data as a flat dictionary
            parent_match: Parent node's match condition (for inheritance)

        Returns:
            Modified transaction dictionary
        """
        rules_list = self.rules.get("rules", [])
        self._process_nodes(rules_list, tx_dict, parent_match)
        return tx_dict

    def _process_nodes(
        self,
        nodes: List[Dict],
        tx_dict: Dict[str, Any],
        parent_match: Optional[Dict] = None,
    ):
        """
        Process a list of rule nodes (siblings).

        Implements stop-on-match semantics: when a node matches, execute its
        actions, recurse into children, then stop processing siblings.
        """
        for node in nodes:
            # Calculate effective match condition (parent AND current)
            current_match = node.get("match", {})
            effective_match = self._combine_match_conditions(
                parent_match, current_match
            )

            # Evaluate the condition
            if self._evaluate_match(effective_match, tx_dict):
                # Execute actions
                apply_actions = node.get("apply", {})
                if apply_actions:
                    self._execute_apply(apply_actions, tx_dict)

                # Recurse into children
                children = node.get("children", [])
                if children:
                    self._process_nodes(children, tx_dict, effective_match)

                # Stop processing siblings (stop-on-match)
                break

    def _combine_match_conditions(
        self, parent_match: Optional[Dict], current_match: Dict
    ) -> Dict:
        """
        Combine parent and current match conditions using AND logic.

        Returns a condition that represents: parent AND current
        """
        if not parent_match:
            return current_match
        if not current_match:
            return parent_match

        # Both exist: create an '$all' expression
        return {"$all": [parent_match, current_match]}

    def _evaluate_match(self, match_expr: Dict, tx_dict: Dict[str, Any]) -> bool:
        """
        Evaluate a match expression against transaction data.

        A match expression can contain:
        - Field predicates: {field: pattern} — all must match (implicit AND)
        - $all: [...] — all sub-expressions must match
        - $any: [...] — at least one sub-expression must match
        - $not: {...} — negates a sub-expression
        - Mixed: {$any: [...], field: pattern} means ($any) AND (field matches)

        Args:
            match_expr: The match expression
            tx_dict: Transaction data

        Returns:
            True if the condition matches, False otherwise
        """
        if not match_expr:
            return True

        # Separate operator keys from field keys
        operator_parts = {}
        field_parts = {}

        for key, value in match_expr.items():
            if key in self._OPERATORS:
                operator_parts[key] = value
            else:
                field_parts[key] = value

        # Evaluate all parts; they are ANDed together
        results = []

        # Evaluate operators
        if "$all" in operator_parts:
            results.append(
                all(
                    self._evaluate_match(sub_expr, tx_dict)
                    for sub_expr in operator_parts["$all"]
                )
            )

        if "$any" in operator_parts:
            results.append(
                any(
                    self._evaluate_match(sub_expr, tx_dict)
                    for sub_expr in operator_parts["$any"]
                )
            )

        if "$not" in operator_parts:
            results.append(
                not self._evaluate_match(operator_parts["$not"], tx_dict)
            )

        # Evaluate field predicates (implicit AND)
        for field, pattern in field_parts.items():
            results.append(self._evaluate_predicate(field, pattern, tx_dict))

        # All parts must be true (AND)
        return all(results) if results else True

    def _evaluate_predicate(
        self, field: str, pattern: str, tx_dict: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single field predicate.

        Matching rules:
        - For set/frozenset fields: "contains" semantics (pattern in set)
        - For string fields with /pattern/: regex search
        - For string fields with plain string: exact match (case-sensitive)

        Args:
            field: Field name to check
            pattern: Pattern to match
            tx_dict: Transaction data

        Returns:
            True if the predicate matches, False otherwise
        """
        # Get field value
        field_value = tx_dict.get(field)

        # Missing field: no match
        if field_value is None:
            return False

        # Set/frozenset field: "contains" semantics
        if isinstance(field_value, (set, frozenset)):
            return pattern in field_value

        # Convert to string if needed
        if not isinstance(field_value, str):
            field_value = str(field_value)

        # Check if pattern is regex (format: /.../)
        if (
            isinstance(pattern, str)
            and pattern.startswith("/")
            and pattern.endswith("/")
        ):
            regex_pattern = pattern[1:-1]  # Remove slashes
            try:
                return bool(re.search(regex_pattern, field_value))
            except re.error:
                return False

        # Plain string: exact match (case-sensitive)
        return str(pattern) == field_value

    def _execute_apply(self, apply_actions: Dict[str, Any], tx_dict: Dict[str, Any]):
        """
        Execute apply actions on transaction dictionary.

        Supports:
        - key: value — set/replace
        - $add: {key: value} — add to list/set
        - $remove: {key: value} — remove from list/set or delete key
        """
        for key, value in apply_actions.items():
            if key == "$add":
                if isinstance(value, dict):
                    for field, val in value.items():
                        self._add_to_field(tx_dict, field, val)
            elif key == "$remove":
                if isinstance(value, dict):
                    for field, val in value.items():
                        self._remove_from_field(tx_dict, field, val)
            else:
                # Set/replace operation
                tx_dict[key] = value

    def _add_to_field(self, tx_dict: Dict[str, Any], key: str, value: Any):
        """
        Add value to a field (list/set semantics with deduplication).
        """
        if key not in tx_dict:
            # Initialize as list
            if isinstance(value, list):
                tx_dict[key] = list(set(value))  # Deduplicate
            else:
                tx_dict[key] = [value]
        else:
            existing = tx_dict[key]

            if isinstance(existing, (set, frozenset)):
                if not isinstance(existing, set):
                    existing = set(existing)
                    tx_dict[key] = existing
                if isinstance(value, list):
                    existing.update(value)
                else:
                    existing.add(value)
            elif isinstance(existing, list):
                # Add to list with deduplication
                if isinstance(value, list):
                    for v in value:
                        if v not in existing:
                            existing.append(v)
                else:
                    if value not in existing:
                        existing.append(value)
            elif isinstance(existing, dict) and isinstance(value, dict):
                # Shallow merge for dicts
                existing.update(value)
            else:
                # Convert to list
                tx_dict[key] = [existing, value]

    def _remove_from_field(self, tx_dict: Dict[str, Any], key: str, value: Any):
        """
        Remove value from a field or delete the key entirely.
        """
        if value is None:
            # Delete the entire key
            tx_dict.pop(key, None)
        elif key in tx_dict:
            existing = tx_dict[key]

            if isinstance(existing, (set, frozenset)):
                if not isinstance(existing, set):
                    existing = set(existing)
                    tx_dict[key] = existing
                if isinstance(value, list):
                    existing.difference_update(value)
                else:
                    existing.discard(value)
            elif isinstance(existing, list):
                # Remove matching elements
                if isinstance(value, list):
                    tx_dict[key] = [v for v in existing if v not in value]
                else:
                    tx_dict[key] = [v for v in existing if v != value]
            elif isinstance(existing, dict):
                # Remove keys from dict
                if isinstance(value, str):
                    existing.pop(value, None)
                elif isinstance(value, list):
                    for v in value:
                        existing.pop(v, None)
