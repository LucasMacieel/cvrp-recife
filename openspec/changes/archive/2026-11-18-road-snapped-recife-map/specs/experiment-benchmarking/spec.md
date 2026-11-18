# Spec Delta

## MODIFIED Requirements

### Requirement: Analytical chart and interactive Recife map generation
The system SHALL generate static visual artifacts of convergence curves and result distributions (boxplots), as well as an interactive HTML map displaying the depot, UBSs/Polyclinics, and vehicle routes in the Recife/PE scenario. When rendering vehicle routes on the interactive Recife HTML map, the system SHALL query road-network driving geometry for each vehicle's ordered stop sequence (starting and ending at the depot) so that route polylines follow actual streets, and SHALL automatically fall back to straight-line node-to-node coordinate segments if road geometry retrieval is disabled, times out, or fails.

#### Scenario: Recife scenario visualization export
- **WHEN** the Recife/PE scenario experiment finishes
- **THEN** the system saves convergence/comparison chart files and an interactive HTML file containing distinct markers for depot and health units and color-coded routes per vehicle

#### Scenario: Road-snapped route polyline rendering
- **WHEN** the interactive Recife map is generated and the road-routing service returns a valid driving geometry for a vehicle route
- **THEN** the route polyline rendered in the HTML map follows the returned street-level coordinates from the depot through each assigned health unit and back to the depot

#### Scenario: Graceful fallback to straight-line route segments
- **WHEN** the interactive Recife map is generated while offline, when the road-routing service returns an error or times out, or when road-geometry lookup is disabled
- **THEN** the system logs a warning (if a request failed) and renders the affected vehicle route polyline using straight-line segments connecting consecutive stop coordinates without aborting map generation
