"""Position calculator for React Flow nodes.

Calculates optimal positions for UML class nodes based on detected bounding boxes
or using intelligent grid layout.
"""

import logging
import math
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

DEFAULT_NODE_WIDTH = 200
DEFAULT_NODE_HEIGHT = 150
GRID_SPACING_X = 300
GRID_SPACING_Y = 250
START_X = 100
START_Y = 100


class PositionCalculator:
    """
    Calculate positions for React Flow nodes.

    Features:
    - Map from detected bounding boxes
    - Grid layout when no boxes available
    - Hierarchical layout based on relationships
    - Overlap prevention

    Example:
        >>> calculator = PositionCalculator()
        >>> nodes = calculator.calculate_positions(nodes, boxes)
    """

    def calculate_positions(
        self,
        nodes: List[Dict[str, any]],
        detected_boxes: List[Dict[str, any]] = None,
    ) -> List[Dict[str, any]]:
        """
        Calculate positions for all nodes.

        Args:
            nodes: List of node dictionaries
            detected_boxes: Optional list of detected bounding boxes

        Returns:
            Nodes with calculated positions

        Example:
            >>> nodes_with_positions = calculator.calculate_positions(nodes)
        """
        if detected_boxes and len(detected_boxes) >= len(nodes):
            return self._map_to_boxes(nodes, detected_boxes)
        else:
            return self._grid_layout(nodes)

    def _map_to_boxes(
        self, nodes: List[Dict[str, any]], boxes: List[Dict[str, any]]
    ) -> List[Dict[str, any]]:
        """
        Map nodes to detected bounding boxes.

        Args:
            nodes: List of nodes
            boxes: List of detected boxes

        Returns:
            Nodes with positions from boxes
        """
        sorted_boxes = sorted(
            boxes, key=lambda b: (b["bbox"][1], b["bbox"][0])
        )

        for i, node in enumerate(nodes):
            if i < len(sorted_boxes):
                bbox = sorted_boxes[i]["bbox"]
                x1, y1, x2, y2 = bbox

                width = x2 - x1
                height = y2 - y1

                node["position"] = {"x": x1, "y": y1}
                node["width"] = max(width, DEFAULT_NODE_WIDTH)
                node["height"] = max(height, DEFAULT_NODE_HEIGHT)
            else:
                fallback_pos = self._calculate_grid_position(i)
                node["position"] = fallback_pos
                node["width"] = DEFAULT_NODE_WIDTH
                node["height"] = DEFAULT_NODE_HEIGHT

        return nodes

    def _grid_layout(self, nodes: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """
        Arrange nodes in grid layout.

        Args:
            nodes: List of nodes

        Returns:
            Nodes with grid positions
        """
        cols = math.ceil(math.sqrt(len(nodes)))

        for i, node in enumerate(nodes):
            row = i // cols
            col = i % cols

            x = START_X + (col * GRID_SPACING_X)
            y = START_Y + (row * GRID_SPACING_Y)

            node["position"] = {"x": x, "y": y}
            node["width"] = DEFAULT_NODE_WIDTH
            node["height"] = DEFAULT_NODE_HEIGHT

        return nodes

    def _calculate_grid_position(self, index: int) -> Dict[str, int]:
        """Calculate grid position for single node."""
        cols = 3
        row = index // cols
        col = index % cols

        x = START_X + (col * GRID_SPACING_X)
        y = START_Y + (row * GRID_SPACING_Y)

        return {"x": x, "y": y}

    def hierarchical_layout(
        self,
        nodes: List[Dict[str, any]],
        edges: List[Dict[str, any]],
    ) -> List[Dict[str, any]]:
        """
        Arrange nodes hierarchically based on relationships.

        Args:
            nodes: List of nodes
            edges: List of edges

        Returns:
            Nodes with hierarchical positions
        """
        node_dict = {node["id"]: node for node in nodes}

        in_degree = {node["id"]: 0 for node in nodes}
        for edge in edges:
            target = edge.get("target")
            if target in in_degree:
                in_degree[target] += 1

        levels = self._assign_levels(nodes, edges, in_degree)

        for node_id, level in levels.items():
            if node_id in node_dict:
                node = node_dict[node_id]

                level_nodes = [
                    nid for nid, lvl in levels.items() if lvl == level
                ]
                index_in_level = level_nodes.index(node_id)

                x = START_X + (index_in_level * GRID_SPACING_X)
                y = START_Y + (level * GRID_SPACING_Y)

                node["position"] = {"x": x, "y": y}
                node["width"] = DEFAULT_NODE_WIDTH
                node["height"] = DEFAULT_NODE_HEIGHT

        return nodes

    def _assign_levels(
        self,
        nodes: List[Dict[str, any]],
        edges: List[Dict[str, any]],
        in_degree: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Assign hierarchy levels using topological sort.

        Args:
            nodes: List of nodes
            edges: List of edges
            in_degree: In-degree count for each node

        Returns:
            Dictionary of node_id -> level
        """
        levels = {}
        current_level = 0

        remaining = set(node["id"] for node in nodes)

        while remaining:
            level_nodes = [
                nid for nid in remaining if in_degree.get(nid, 0) == 0
            ]

            if not level_nodes:
                for nid in remaining:
                    levels[nid] = current_level
                break

            for node_id in level_nodes:
                levels[node_id] = current_level
                remaining.remove(node_id)

                for edge in edges:
                    if edge.get("source") == node_id:
                        target = edge.get("target")
                        if target in in_degree:
                            in_degree[target] -= 1

            current_level += 1

        return levels

    def prevent_overlaps(
        self, nodes: List[Dict[str, any]], min_distance: int = 50
    ) -> List[Dict[str, any]]:
        """
        Adjust positions to prevent node overlaps.

        Args:
            nodes: List of nodes
            min_distance: Minimum distance between nodes

        Returns:
            Nodes with adjusted positions
        """
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                if self._is_overlapping(node1, node2, min_distance):
                    self._resolve_overlap(node1, node2, min_distance)

        return nodes

    def _is_overlapping(
        self,
        node1: Dict[str, any],
        node2: Dict[str, any],
        min_distance: int,
    ) -> bool:
        """Check if two nodes overlap."""
        pos1 = node1["position"]
        pos2 = node2["position"]

        w1 = node1.get("width", DEFAULT_NODE_WIDTH)
        h1 = node1.get("height", DEFAULT_NODE_HEIGHT)
        w2 = node2.get("width", DEFAULT_NODE_WIDTH)
        h2 = node2.get("height", DEFAULT_NODE_HEIGHT)

        return not (
            pos1["x"] + w1 + min_distance < pos2["x"]
            or pos2["x"] + w2 + min_distance < pos1["x"]
            or pos1["y"] + h1 + min_distance < pos2["y"]
            or pos2["y"] + h2 + min_distance < pos1["y"]
        )

    def _resolve_overlap(
        self,
        node1: Dict[str, any],
        node2: Dict[str, any],
        min_distance: int,
    ) -> None:
        """Resolve overlap by moving node2."""
        pos1 = node1["position"]
        pos2 = node2["position"]

        w1 = node1.get("width", DEFAULT_NODE_WIDTH)

        pos2["x"] = pos1["x"] + w1 + min_distance
