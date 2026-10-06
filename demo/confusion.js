window.DEMO_CONFUSION = {
 "V1": {
  "confusion": [
   [
    6,
    0,
    1
   ],
   [
    0,
    2,
    5
   ],
   [
    3,
    1,
    13
   ]
  ],
  "recall": [
   0.8571428571428571,
   0.2857142857142857,
   0.7647058823529411
  ],
  "n": [
   7,
   7,
   17
  ]
 },
 "V1 + V2": {
  "confusion": [
   [
    6,
    1,
    0
   ],
   [
    0,
    4,
    3
   ],
   [
    2,
    3,
    12
   ]
  ],
  "recall": [
   0.8571428571428571,
   0.5714285714285714,
   0.7058823529411765
  ],
  "n": [
   7,
   7,
   17
  ]
 },
 "note": "rows = true batch, columns = called batch; each spot called by a model that never saw it (5 folds by spot)",
 "fusion": {
  "v1_dims": 1536,
  "v2_dims": 512,
  "members": [
   "v2",
   "v2s1",
   "v2s2",
   "v2_noseg"
  ],
  "late": 0.711484593837535,
  "v1": 0.6358543417366946,
  "joint_scratch": 0.6274509803921569,
  "joint_warm": 0.6554621848739496
 }
};
