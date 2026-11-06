# ChargeWise | EV Charging Capacity Analytics

An EV workplace charging analytics dashboard for utilization analysis, capacity planning, queueing evaluation, and hypothetical policy scenarios using ACN-Data.

## Feasibility Assessment and Study Scope

The initial feasibility assessment identified the pre-disruption
period as the primary capacity-analysis period for Caltech and JPL.

### Primary analysis

Raw session records in the pre-disruption period:

- Caltech: 27,584 records across 95 eligible weeks.
- JPL: 25,069 records across 76 eligible weeks.

### Secondary analysis

Raw session records in the recovery period:

- Caltech: 3,307 records across 43 eligible weeks.
- JPL: 6,400 raw records across 43 eligible weeks.

The JPL recovery count includes two known conflicting records
at the same station and connection timestamp. Both records
are excluded from the primary cleaned capacity replay,
which retains 6,398 JPL recovery sessions.

### Capacity-pressure screening

A week was flagged when its weekday business-hour peak occupancy
reached at least 80% of the assumed capacity. The screening gate
required at least 10% of eligible weeks with observed sessions
to meet this threshold.

- Caltech pre-disruption: 20 of 95 weeks (21.05%).
- JPL pre-disruption: 74 of 76 weeks (97.37%) under both
  50-port and 52-port assumptions.

This screening identifies high observed utilization. It does not
establish actual queues, rejected arrivals, or unmet demand.

### Capacity inventory limitations

JPL has 52 unique station IDs in the historical session records,
and reconstructed occupancy reaches 52 simultaneously occupied
station IDs. The difference between this historical observation
and the currently published 50-EVSE inventory remains unresolved.

Caltech uses a provisional 54-port Level 2 denominator.
An additional station with 1,130 sessions is excluded from
that denominator because its equipment type is unverified.

All capacity figures must be labelled as provisional where
the historical usable inventory has not been independently
confirmed.
