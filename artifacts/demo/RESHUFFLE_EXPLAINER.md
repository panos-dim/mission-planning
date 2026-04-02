# Reshuffle Explainer

## Revision Summary
| Field | Value |
| --- | --- |
| Workspace | workspace_demo |
| Revision | 3 |
| Previous Revision | 2 |
| Mode Used | repair |
| Plan ID | plan_demo |
| Commit Type | repair |
| Generated At | 2026-04-02T14:20:42.202851Z |

## Explanation
- Revision 3 applied in repair mode against revision 2.
- Active schedule size changed from 2 to 2 acquisitions.
- 1 added, 1 removed, 1 kept.
- 1 kept acquisitions changed timing and 1 changed satellite assignment.
- Added targets: PORT_C.
- Removed targets: PORT_B.
- Timing changes: PORT_A: 2026-04-02T10:00:00Z -> 2026-04-02T10:15:00Z.
- Satellite reassignments: PORT_A: SAT-A -> SAT-B.

## Diff Summary
| Metric | Count |
| --- | --- |
| Before | 2 |
| After | 2 |
| Added | 1 |
| Removed | 1 |
| Kept | 1 |
| Timing Changed | 1 |
| Satellite Changed | 1 |

## Added Acquisitions
| Target | Planner Target | Canonical Target | Order | Template | Instance | Satellite | Start | End |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORT_C | planner::PORT_C::2026-04-02 | PORT_C | ord_port_c | tmpl_port_c | PORT_C:2026-04-02 | SAT-D | 2026-04-02T12:00:00Z | 2026-04-02T12:05:00Z |

## Removed Acquisitions
| Target | Planner Target | Canonical Target | Order | Template | Instance | Satellite | Start | End |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORT_B | planner::PORT_B::2026-04-02 | PORT_B | ord_port_b | tmpl_port_b | PORT_B:2026-04-02 | SAT-C | 2026-04-02T11:00:00Z | 2026-04-02T11:05:00Z |

## Kept Acquisitions
| Target | Planner Target | Canonical Target | Order | Template | Instance | Satellite Before | Satellite After | Start Before | Start After | Changes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORT_A | planner::PORT_A::2026-04-02 | PORT_A | ord_port_a | tmpl_port_a | PORT_A:2026-04-02 | SAT-A | SAT-B | 2026-04-02T10:00:00Z | 2026-04-02T10:15:00Z | timing,satellite_assignment |

## Changed Timing
| Target | Planner Target | Canonical Target | Order | Template | Instance | Satellite Before | Satellite After | Start Before | Start After | Changes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORT_A | planner::PORT_A::2026-04-02 | PORT_A | ord_port_a | tmpl_port_a | PORT_A:2026-04-02 | SAT-A | SAT-B | 2026-04-02T10:00:00Z | 2026-04-02T10:15:00Z | timing,satellite_assignment |

## Changed Satellite Assignment
| Target | Planner Target | Canonical Target | Order | Template | Instance | Satellite Before | Satellite After | Start Before | Start After | Changes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORT_A | planner::PORT_A::2026-04-02 | PORT_A | ord_port_a | tmpl_port_a | PORT_A:2026-04-02 | SAT-A | SAT-B | 2026-04-02T10:00:00Z | 2026-04-02T10:15:00Z | timing,satellite_assignment |
