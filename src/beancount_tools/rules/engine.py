"""
Rule Engine for Tree Rules v1 Specification

Implements the tree-based rule matching and action execution system
according to the README.md specification.
"""

import re
import yaml
from typing import Any, Dict, List, Optional, Union


class RuleEngine:
    """Engine for parsing and applying tree-based rules to transactions."""

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
        self, tx_dict: Dict[str, Any], parent_when: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Apply rules to a transaction dictionary.

        Args:
            tx_dict: Transaction data as a flat dictionary
            parent_when: Parent node's when condition (for inheritance)

        Returns:
            Modified transaction dictionary
        """
        rules_list = self.rules.get("rules", [])
        self._process_nodes(rules_list, tx_dict, parent_when)
        return tx_dict

    def _process_nodes(
        self,
        nodes: List[Dict],
        tx_dict: Dict[str, Any],
        parent_when: Optional[Dict] = None,
    ):
        """
        Process a list of rule nodes (siblings).

        Implements stop-on-match semantics: when a node matches, execute its actions,
        recurse into children, then stop processing siblings.
        """
        for node in nodes:
            # Calculate effective when condition (parent AND current)
            current_when = node.get("when", {})
            effective_when = self._combine_when_conditions(parent_when, current_when)

            # Evaluate the condition
            if self._evaluate_when(effective_when, tx_dict):
                # Execute actions
                then_actions = node.get("then", {})
                if then_actions:
                    self._execute_then(then_actions, tx_dict)

                # Recurse into children
                children = node.get("children", [])
                if children:
                    self._process_nodes(children, tx_dict, effective_when)

                # Stop processing siblings (stop-on-match)
                break

    def _combine_when_conditions(
        self, parent_when: Optional[Dict], current_when: Dict
    ) -> Dict:
        """
        Combine parent and current when conditions using AND logic.

        Returns a condition that represents: parent AND current
        """
        if not parent_when:
            return current_when
        if not current_when:
            return parent_when

        # Both exist: create an 'all' expression
        return {"all": [parent_when, current_when]}

    def _evaluate_when(self, when_expr: Dict, tx_dict: Dict[str, Any]) -> bool:
        """
        Evaluate a when expression against transaction data.

        Args:
            when_expr: The when expression (can be atomic map, all/any/not, or empty)
            tx_dict: Transaction data

        Returns:
            True if the condition matches, False otherwise
        """
        if not when_expr:
            return True

        # Check for logical operators
        if "all" in when_expr:
            return all(
                self._evaluate_when(sub_expr, tx_dict) for sub_expr in when_expr["all"]
            )

        if "any" in when_expr:
            return any(
                self._evaluate_when(sub_expr, tx_dict) for sub_expr in when_expr["any"]
            )

        if "not" in when_expr:
            return not self._evaluate_when(when_expr["not"], tx_dict)

        # Atomic condition map: all predicates must match (implicit AND)
        for field, pattern in when_expr.items():
            if not self._evaluate_predicate(field, pattern, tx_dict):
                return False

        return True

    def _evaluate_predicate(
        self, field: str, pattern: str, tx_dict: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single field predicate.

        Args:
            field: Field name to check
            pattern: Pattern to match (regex or substring)
            tx_dict: Transaction data

        Returns:
            True if the predicate matches, False otherwise
        """
        # Get field value
        field_value = tx_dict.get(field)

        # Missing field: no match
        if field_value is None:
            return False

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

        # Substring match (case-insensitive)
        return pattern.lower() in field_value.lower()

    def _execute_then(self, then_actions: Dict[str, Any], tx_dict: Dict[str, Any]):
        """
        Execute then actions on transaction dictionary.

        Supports:
        - key: value (set/replace)
        - +key: value (add to list/set)
        - -key: value (remove from list or delete key)
        """
        for key, value in then_actions.items():
            if key.startswith("+"):
                # Add operation
                actual_key = key[1:]
                self._add_to_field(tx_dict, actual_key, value)
            elif key.startswith("-"):
                # Remove operation
                actual_key = key[1:]
                self._remove_from_field(tx_dict, actual_key, value)
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

            if isinstance(existing, list):
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
            elif isinstance(existing, (set, frozenset)):
                if not isinstance(existing, set):
                    existing = set(existing)
                    tx_dict[key] = existing
                if isinstance(value, list):
                    existing.update(value)
                else:
                    existing.add(value)
            else:
                # Convert to list or replace
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

            if isinstance(existing, list):
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
