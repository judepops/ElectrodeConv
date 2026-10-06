# Seam examples: image tiles that join across batch folders

Some of the 31 images are neighbouring tiles cut from one longer strip, and three of those strips are split across batch folders. These pictures show it. Use them when asking Polaron how tiles were assigned to batches.

Each side is tinted by its batch folder (orange = Batch_1, blue = Batch_2, green = Batch_3). The dashed yellow line is the edge between two image files. The tint and the brightening are for display only; they are not in the data.

| File | What it shows |
|---|---|
| `00_A_strip_height2080.jpg` | One continuous piece of material filed as Batch_3, Batch_2 and Batch_1 (`cfe5vt7s`, `r17byphk`, `ffwubibz`). Show this one first. |
| `00_B_strip_height2068.jpg` | Four tiles: three in Batch_3, the last in Batch_2 (`vc2whyaq`, `x77cy643`, `utfgcjfa`, `rxax5ozo`) |
| `00_C_strip_height2148.jpg` | Two tiles: Batch_1 and Batch_2 (`f1vzngrs`, `epqdaau9`) |
| `01`–`04_JOIN_*.jpg` | Close-ups of the four joins that cross batch folders, at full resolution (25 nm per pixel, 900 px each side) |
| `05`–`06_JOIN_within_Batch_3_*.jpg` | Two ordinary joins between Batch_3 tiles, for reference |
| `07`–`08_NOT_A_JOIN_*.jpg` | Two pairs with the same image height in different folders that are not neighbours: shapes are cut off at the line |

## The evidence

For each pair, the last 4 pixel columns of the left tile were compared with the first 4 of the right tile (BSE detector, channel 0, allowing a vertical shift of up to 40 px).

- 12 joins link 18 of the 31 images. All score 0.83–0.97 (1.0 = identical edges).
- 4 of the 12 cross batch folders, on 3 strips. They score 0.89–0.92.
- 80 random unrelated pairs with the same search: mean 0.10, highest 0.49.
- The two same-height, mixed-folder pairs that are not neighbours (heights 2156 and 2272) score 0.03–0.23.

The other 13 images have no proven neighbour. Grouping all 31 into 13 "sessions" rests on shared image height and resolution tag, which is weaker evidence than a pixel-level join.
