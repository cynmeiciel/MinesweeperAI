# Experiment Tables

All times are milliseconds. Percentiles use linear interpolation with position `(n - 1) * q`.

## Solver and preset

| experiment_id | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_time_ms |
|---|---|---|---|---|---|---|---|---|
| random_5x5-3_opening_random_bfs_outside0 | 5 | 0 | 5 | 0 | 0.0 | 0.0 | 0.43449149475208104 | 0.1456 |
| random_9x9-10_opening_random_bfs_outside0 | 5 | 0 | 5 | 0 | 0.0 | 0.0 | 0.43449149475208104 | 0.285 |
| random_16x16-40_opening_random_bfs_outside0 | 5 | 0 | 5 | 0 | 0.0 | 0.0 | 0.43449149475208104 | 0.827 |
| random_16x30-99_opening_random_bfs_outside0 | 5 | 0 | 5 | 0 | 0.0 | 0.0 | 0.43449149475208104 | 1.2606 |
| lv1_5x5-3_opening_center_bfs_outside0 | 5 | 3 | 0 | 2 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 0.221 |
| lv1_9x9-10_opening_center_bfs_outside0 | 5 | 4 | 0 | 1 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 5.696400000000001 |
| lv1_16x16-40_opening_center_bfs_outside0 | 5 | 1 | 0 | 4 | 0.2 | 0.03622316096978745 | 0.6244717358814613 | 58.859 |
| lv1_16x30-99_opening_center_bfs_outside0 | 5 | 0 | 0 | 5 | 0.0 | 0.0 | 0.43449149475208104 | 24.0364 |
| lv2_5x5-3_opening_center_bfs_outside0 | 5 | 3 | 0 | 2 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 0.3352 |
| lv2_9x9-10_opening_center_bfs_outside0 | 5 | 4 | 0 | 1 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 3.0544 |
| lv2_16x16-40_opening_center_bfs_outside0 | 5 | 4 | 0 | 1 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 59.0044 |
| lv2_16x30-99_opening_center_bfs_outside0 | 5 | 0 | 0 | 5 | 0.0 | 0.0 | 0.43449149475208104 | 66.7462 |
| lv3_5x5-3_opening_center_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 0.5042 |
| lv3_9x9-10_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.044 |
| lv3_16x16-40_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 50.65 |
| lv3_16x30-99_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 416.8532 |

## First-click rules

| experiment_id | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_time_ms |
|---|---|---|---|---|---|---|---|---|
| lv3_9x9-10_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.044 |
| lv3_9x9-10_unsafe_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 2.3154 |
| lv3_9x9-10_safe_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 2.9792 |

## Density

| experiment_id | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_time_ms |
|---|---|---|---|---|---|---|---|---|
| lv3_9x9-10_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.044 |
| lv3_9x9-5_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 1.0528 |
| lv3_9x9-6_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 1.5462 |
| lv3_9x9-7_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 2.1068000000000002 |
| lv3_9x9-8_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 2.4466 |
| lv3_9x9-9_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 2.609 |
| lv3_9x9-11_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 2.8486000000000002 |
| lv3_9x9-12_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 3.5572 |
| lv3_9x9-13_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 3.5183999999999997 |
| lv3_9x9-14_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 5.9606 |
| lv3_9x9-15_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 8.2482 |
| lv3_9x9-16_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 7.868399999999999 |
| lv3_9x9-17_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 15.8728 |
| lv3_9x9-18_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 33.6688 |
| lv3_9x9-19_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 112.14280000000001 |
| lv3_9x9-20_opening_center_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 6.3434 |
| lv3_9x9-21_opening_center_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 7.6604 |
| lv3_9x9-22_opening_center_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 7.534 |
| lv3_9x9-23_opening_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 16.0372 |
| lv3_9x9-24_opening_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 18.165 |

## Flood fill

| experiment_id | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_time_ms |
|---|---|---|---|---|---|---|---|---|
| lv3_9x9-10_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.044 |
| lv3_9x9-10_opening_center_dfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 2.9922 |

## Center and corner

| experiment_id | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_time_ms |
|---|---|---|---|---|---|---|---|---|
| lv3_9x9-10_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.044 |
| lv3_9x9-10_safe_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 2.9792 |
| lv3_9x9-10_safe_corner_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 3.0874 |
| lv3_9x9-10_opening_corner_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 4.4868 |

## Frontier and outside

| experiment_id | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_time_ms |
|---|---|---|---|---|---|---|---|---|
| lv3_9x9-10_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.044 |
| lv3_16x16-40_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 50.65 |
| lv3_16x30-99_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 416.8532 |
| lv3_9x9-10_opening_center_bfs_outside1 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.0354 |
| lv3_16x16-40_opening_center_bfs_outside1 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 46.4324 |
| lv3_16x30-99_opening_center_bfs_outside1 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 440.9558 |

## LV3 timing

| experiment_id | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_time_ms |
|---|---|---|---|---|---|---|---|---|
| lv3_5x5-3_opening_center_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 0.5042 |
| lv3_9x9-10_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.044 |
| lv3_16x16-40_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 50.65 |
| lv3_16x30-99_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 416.8532 |
| lv3_9x9-10_unsafe_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 2.3154 |
| lv3_9x9-10_safe_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 2.9792 |
| lv3_9x9-5_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 1.0528 |
| lv3_9x9-6_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 1.5462 |
| lv3_9x9-7_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 2.1068000000000002 |
| lv3_9x9-8_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 2.4466 |
| lv3_9x9-9_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 2.609 |
| lv3_9x9-11_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 2.8486000000000002 |
| lv3_9x9-12_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 3.5572 |
| lv3_9x9-13_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 3.5183999999999997 |
| lv3_9x9-14_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 5.9606 |
| lv3_9x9-15_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 8.2482 |
| lv3_9x9-16_opening_center_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 7.868399999999999 |
| lv3_9x9-17_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 15.8728 |
| lv3_9x9-18_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 33.6688 |
| lv3_9x9-19_opening_center_bfs_outside0 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 112.14280000000001 |
| lv3_9x9-20_opening_center_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 6.3434 |
| lv3_9x9-21_opening_center_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 7.6604 |
| lv3_9x9-22_opening_center_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 7.534 |
| lv3_9x9-23_opening_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 16.0372 |
| lv3_9x9-24_opening_center_bfs_outside0 | 5 | 2 | 3 | 0 | 0.4 | 0.1176182311592533 | 0.769280067791163 | 18.165 |
| lv3_9x9-10_opening_center_dfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 2.9922 |
| lv3_9x9-10_safe_corner_bfs_outside0 | 5 | 3 | 2 | 0 | 0.6 | 0.23071993220883708 | 0.8823817688407467 | 3.0874 |
| lv3_9x9-10_opening_corner_bfs_outside0 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 4.4868 |
| lv3_9x9-10_opening_center_bfs_outside1 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 3.0354 |
| lv3_16x16-40_opening_center_bfs_outside1 | 5 | 5 | 0 | 0 | 1.0 | 0.5655085052479191 | 1.0 | 46.4324 |
| lv3_16x30-99_opening_center_bfs_outside1 | 5 | 4 | 1 | 0 | 0.8 | 0.3755282641185388 | 0.9637768390302125 | 440.9558 |
