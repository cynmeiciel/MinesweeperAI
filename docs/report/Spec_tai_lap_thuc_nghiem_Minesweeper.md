# Spec tái lập thực nghiệm Minesweeper AI

## 1. Mục tiêu và phạm vi

Tạo quy trình chạy thí nghiệm, lưu CSV từng ván, tổng hợp bảng và vẽ biểu đồ cho Chương 4 của báo cáo.

- Tận dụng `minesweeper.analysis.batch`: `run_game`, `write_csv`, `wilson_interval` và các trường của `GameRecord`.
- Giữ nguyên hành vi mặc định của Random, LV1, LV2, LV3.
- Bổ sung cấu hình thí nghiệm cho mở đầu ở góc và xét ô ngoài frontier.
- Không thêm ablation, DFSStats, timeout, cache hoặc sửa thuật toán propagation trong phạm vi này.
- Kết quả mới phải được tạo từ lần chạy thực tế. Không điền hoặc điều chỉnh kết quả để khớp số liệu cũ.

## 2. Các tệp cần tạo

| Tệp | Trách nhiệm |
|---|---|
| `docs/report/scripts/run_experiments.py` | Chạy các cấu hình, ghi CSV từng ván và thông tin lần chạy. |
| `docs/report/scripts/summarize_results.py` | Đọc CSV để tạo bảng tổng hợp, thống kê thời gian và đối chiếu biến thể. |
| `docs/report/scripts/plot_results.py` | Vẽ biểu đồ từ dữ liệu đã tổng hợp. |
| `docs/report/README.md` | Hướng dẫn cài đặt, chạy, cấu hình và ánh xạ kết quả sang báo cáo. |
| `docs/report/data/` | Chứa dữ liệu và thông tin lần chạy được sinh tự động. |

Các script phải tìm được thư mục gốc repo từ vị trí của chúng, không phụ thuộc thư mục làm việc hiện tại. Dùng thư viện chuẩn cho chạy/tổng hợp; dùng matplotlib để vẽ. Ghi các phụ thuộc và phiên bản cần thiết trong README.

## 3. Những sửa đổi tối thiểu trong code hiện tại

### 3.1 Cấu hình vị trí mở đầu

- Thêm tham số keyword `opening_strategy="center"` vào constructor của `RuleBasedSolver`, `ConstraintSolver`, `DfsSolver`.
- Giá trị hợp lệ: `center`, `corner`.
- LV3 truyền lựa chọn xuống LV2; LV2 truyền xuống LV1.
- `center`: giữ nguyên quy tắc chọn ô gần tâm và cách phá hòa hiện tại.
- `corner`: chọn `(0, 0)` ở lần mở đầu; nếu ô này không phải ứng viên hợp lệ, dùng quy tắc gần tâm hiện tại.
- Chỉ thay đổi nước mở đầu; các nước sau giữ nguyên.
- Random giữ nguyên hành vi; cấu hình vị trí mở đầu của Random ghi là `random`.

### 3.2 Cấu hình ứng viên ngoài frontier

- Thêm keyword `include_outside=False` vào constructor của `DfsSolver`.
- Trong `next_move`, truyền cấu hình này vào `_global_probabilities` thay cho giá trị `False` cố định.
- Không viết lại công thức xác suất: hàm hiện tại đã hỗ trợ `include_outside=True`.
- Các ứng viên ngoài frontier được xử lý bằng `_choose_move` hiện có. Giữ nguyên quy tắc chọn nước chắc chắn, xác suất nhỏ nhất, INFO và tọa độ.

### 3.3 Khởi tạo solver trong batch

- Cho phép `run_game` nhận thêm một solver factory tùy chọn qua keyword, để script tạo solver với các cấu hình trên.
- Nếu không truyền factory, giữ nguyên cách gọi `solver_cls(solver_rng(config.seed))`.
- Giữ tương thích với các lời gọi và CLI hiện có. Không bắt buộc mở rộng CLI `python -m minesweeper.analysis`; các lựa chọn mới có thể chỉ được cung cấp qua `run_experiments.py`.
- Không sửa cách đếm `guesses` trong đợt thay đổi này. Ghi rõ nó đang đếm `certain=False`, và Opening dưới UNSAFE hiện chưa được tính vào guesses.

## 4. Script chạy thí nghiệm

### Giao diện

```bash
python docs/report/scripts/run_experiments.py --suite all --out-dir docs/report/data/run_001
```

Tham số:

- `--suite`: `all`, `main`, `first-click`, `density`, `flood-fill`, `corner`, `outside`.
- `--out-dir`: thư mục riêng cho lần chạy; bắt buộc.
- `--seed-start`: seed đầu tiên, mặc định `0`.
- `--games`: tùy chọn ghi đè số ván cho mỗi cấu hình, dùng khi chạy thử. Khi không truyền, dùng cỡ mẫu trong bảng dưới.

### Ma trận thí nghiệm

| Nhóm | Cấu hình | Số ván mỗi cấu hình |
|---|---|---|
| `main` | Random/LV1/LV2/LV3 × tiny 5×5–3 mìn, beginner 9×9–10 mìn, intermediate 16×16–40 mìn | 1.000 |
| `main` | Random/LV1/LV2/LV3 × expert 16×30–99 mìn | 300 |
| `first-click` | LV3, beginner × OPENING/SAFE/UNSAFE | 1.000 |
| `density` | LV3, 9×9, số mìn nguyên từ 5 đến 24, bao gồm hai đầu | 500 |
| `flood-fill` | LV3, beginner × BFS/DFS | 1.000 |
| `corner` | LV3, beginner × center/corner × SAFE/OPENING | 1.000 |
| `outside` | LV3, beginner/intermediate × include_outside=False/True | 1.000 |
| `outside` | LV3, expert × include_outside=False/True | 300 |

Mặc định cho mọi cấu hình nếu không ghi khác: OPENING, bật chord, flood-fill BFS, mở gần tâm, `include_outside=False`. Seed ván thứ i là `seed_start + i`.

- Dùng số mìn nguyên cho nhóm mật độ; mật độ thực tế là `mines / (rows * cols)`, tránh sai lệch do làm tròn từ phần trăm.
- Khi chạy `all`, tái sử dụng các cấu hình trùng hoàn toàn giữa các nhóm. Không gộp hai lần chạy cùng cấu hình thành mẫu lớn hơn.
- Mỗi cấu hình có mã định danh ổn định; tên CSV phản ánh solver, kích thước/số mìn, luật mở đầu, vị trí mở đầu, BFS/DFS và lựa chọn outside.
- Không ghi đè dữ liệu có sẵn. Nếu thư mục đích đã chứa kết quả, báo lỗi và yêu cầu dùng thư mục khác.
- In tiến độ theo cấu hình. Sau mỗi ván hoàn tất, ghi và flush một dòng CSV để giữ phần dữ liệu đã chạy nếu bị ngắt.
- Ghi số ván dự kiến và số ván thực sự hoàn tất; chỉ đánh dấu hoàn tất sau khi đủ số ván. Không coi dữ liệu bị ngắt là thí nghiệm đầy đủ.

## 5. Dữ liệu và thông tin lần chạy

### CSV từng cấu hình

Giữ đủ các trường hiện có của `GameRecord`:

```text
seed, rows, cols, mines, density, first_click, chord, flood_fill,
solver, result, moves, guesses, cells_revealed,
mines_remaining, cells_remaining, time_ms
```

Thêm vào CSV do script tạo: `experiment_id`, `opening_strategy`, `include_outside`. Dùng UTF-8, header đầy đủ; kết quả chỉ nhận `won`, `lost`, `stalled`.

### `manifest.json`

Ghi phiên bản schema, commit Git, trạng thái working tree, Python, hệ điều hành, CPU nếu lấy được, thời gian bắt đầu/kết thúc có timezone và lệnh chạy. Nếu working tree có thay đổi, lưu patch tương ứng cùng lần chạy để xác định được code đã dùng; nếu không có Git, ghi rõ commit không xác định.

Với mỗi cấu hình, ghi đầy đủ các tùy chọn, seed đầu/cuối, số ván dự kiến/hoàn tất, đường dẫn CSV tương đối và trạng thái hoàn tất. Không giả lập thông tin môi trường nếu không lấy được.

## 6. Script tổng hợp

```bash
python docs/report/scripts/summarize_results.py --data-dir docs/report/data/run_001
```

- Đọc manifest và CSV; kiểm tra schema, cấu hình, seed trùng/thiếu và số ván hoàn tất.
- Mặc định báo lỗi nếu dữ liệu chưa đầy đủ; không xuất bảng chính thức từ một lần chạy bị ngắt.
- Nhóm theo toàn bộ cấu hình, gồm `opening_strategy` và `include_outside`. Không chỉ nhóm theo tên `lv3`.
- Xuất `summary.csv` và `tables.md` trong thư mục lần chạy.
- Mỗi dòng tổng hợp gồm: cấu hình, số ván, thắng/thua/bế tắc, tỉ lệ thắng, Wilson 95%, nước trung bình, đoán trung bình, thời gian trung bình/trung vị/phân vị 95/lớn nhất.
- Dùng `wilson_interval` hiện có. Tính phân vị 95 bằng một phương pháp cố định và ghi phương pháp trong README.
- Các bảng Markdown tương ứng: solver/preset; luật click đầu; mật độ; BFS/DFS; center/corner; frontier/outside; thời gian LV3.
- Ghi rõ đơn vị ms và cỡ mẫu. Không làm tròn số trước khi tính thống kê.
- Không kết luận ý nghĩa thống kê chỉ từ việc các khoảng Wilson chồng lấn. Kiểm định chênh lệch và ablation nằm ngoài phạm vi spec này.

## 7. Script vẽ biểu đồ

```bash
python docs/report/scripts/plot_results.py --data-dir docs/report/data/run_001
```

- Đọc `summary.csv`, không chứa số liệu viết cứng.
- Xuất vào thư mục `figures/` của lần chạy, định dạng PNG tối thiểu 300 DPI và SVG.
- `win_rate_by_solver`: biểu đồ cột nhóm theo preset, màu theo solver, kèm Wilson 95%.
- `win_rate_by_density`: mật độ thực tế trên trục x, tỉ lệ thắng LV3 trên trục y, kèm khoảng Wilson 95%.
- Trục tỉ lệ thắng từ 0 đến 100%; ghi tên trục, chú giải, luật mở đầu và cỡ mẫu. Không chỉ dùng màu để phân biệt các solver.
- Không suy đoán dữ liệu thiếu hoặc vẽ biến thể không có kết quả. Báo rõ nhóm dữ liệu cần bổ sung.
- Ghi ánh xạ tên biểu đồ sang Hình 4.1 và Hình 4.2 trong README.

## 8. Nội dung README và phụ lục báo cáo

README phải có:

1. Cài đặt và phiên bản phụ thuộc; lệnh chạy thử và lệnh chạy đủ bộ.
2. Ma trận cấu hình, quy tắc seed và ý nghĩa các trường CSV.
3. Cách tạo bảng, biểu đồ từ một thư mục lần chạy.
4. Ánh xạ từng bảng/hình trong báo cáo sang nhóm thí nghiệm và tệp đầu ra.
5. Giới hạn: cùng seed chỉ bảo đảm cùng bàn nếu các điều kiện sinh bàn và ô mở đầu giống nhau; center/corner dưới SAFE/OPENING có thể sinh bàn khác.
6. Thời gian phụ thuộc máy và môi trường; không yêu cầu số thời gian khớp tuyệt đối giữa các lần chạy.
7. Giới hạn diễn giải `guesses` dưới UNSAFE và `stalled` có thể gồm lỗi thực thi/nước không hợp lệ.

Phụ lục báo cáo chỉ cần ghi link repo, commit của lần đo, thư mục dữ liệu, các lệnh tái lập và dẫn đến README. Mục 4.1 dẫn sang phụ lục. Khi có kết quả mới, cập nhật bảng và biểu đồ từ kết quả mới; giữ tách biệt với dữ liệu lịch sử.

## 9. Tiêu chí nghiệm thu

- Chạy thử `main` với `--games 5` tạo đúng 5 dòng cho mỗi cấu hình và metadata ghi rõ cỡ mẫu đã ghi đè.
- Chạy lại cùng cấu hình, seed và phiên bản code trong thư mục mới cho cùng kết quả, moves, guesses, cells_revealed; không yêu cầu time_ms giống nhau.
- `center` và `include_outside=False` giữ nguyên hành vi mặc định và các kiểm thử hiện có.
- `corner` mở `(0, 0)` ở ván trống; `include_outside=True` xét được ô ngoài frontier an toàn trong ví dụ `# 1 # # #` có một mìn.
- Tổng thắng + thua + bế tắc bằng số dòng; mọi tỉ lệ, thống kê và hình được tính từ CSV.
- Không trộn baseline và biến thể; không đếm lại cấu hình được dùng chung giữa nhiều nhóm.
- CSV chưa đủ số ván được phát hiện, không tạo bảng chính thức âm thầm.
- Một người khác làm theo README có thể chạy thí nghiệm và tạo lại các bảng/hình mà không sửa tay script.
