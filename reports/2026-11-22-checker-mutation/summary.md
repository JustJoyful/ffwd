# Checker mutation self-test (dev tasks, seeded sample)

60 tasks sampled; 60 reference outputs passed their own spec and were mutated; unmutated control failures: 0.

| mutant | applicable | killed (check failed) | survivors |
|---|---|---|---|
| truncate_half | 60 | 58 | 2 |
| wrong_width | 44 | 44 | 0 |
| wrong_container_mkv | 60 | 60 | 0 |
| empty_file | 60 | 60 | 0 |
| garbage_file | 60 | 60 | 0 |
| wrong_fps | 7 | 7 | 0 |
| rotate_180 | 12 | 12 | 0 |
| lossless_claimed_but_reencoded | 7 | 7 | 0 |
| louder_audio | 3 | 3 | 0 |

A survivor is a checker blind spot: 2 found, listed in results.json.
