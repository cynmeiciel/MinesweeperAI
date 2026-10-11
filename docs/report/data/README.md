# Các lần chạy

## Bộ chính thức: full_20261011

Đã chạy đủ 43 cấu hình duy nhất, 30.000 ván. Ma trận không ghi đè cỡ mẫu;
seed bắt đầu từ 0. Thời điểm và Python/OS được ghi trong manifest theo timezone
UTC. CPU quan sát sau lần chạy được ghi rõ nguồn trong validation.json.

- `manifest.json`: schema 2, nền commit 0c1622a, working tree dirty,
  cấu hình, số ván/seed, group_games và checksum.
- `*.csv` theo experiment_id: 30.000 dòng GameRecord có metadata biến thể.
- `source_snapshot.zip` và `working_tree.patch`: mã Python thực chạy và các
  chỉnh sửa tracked. Không chỉ dùng commit nền để mô tả phiên bản script.
- `summary.csv`: 43 dòng cho các cấu hình duy nhất.
- `group_summary.csv`: 51 dòng theo nhóm; có dùng lại cùng CSV với seed prefix
  đúng cỡ mẫu. Không cộng các dòng này để tính số ván độc lập.
- `tables.md`: các bảng từ CSV, có coverage và thời gian mean/median/p95/max.
- `figures/`: Hình 4.1, 4.2 dạng PNG 300 DPI và SVG.
- `run.log`: log toàn bộ benchmark, không có cảnh báo batch bất thường.
- `validation.json`: xác minh schema/checksum, 30.000 dòng, đối chiếu smoke,
  khôi phục source snapshot, BFS/DFS và giới hạn phạm vi.
- `derived_provenance.json`: phiên bản và hash script tạo bảng/hình sau chạy.

16/16 số ván thắng trong bảng chính khớp bản báo cáo người dùng cung cấp.
LV3 lần lượt đạt 899/1.000, 961/1.000, 870/1.000 và 144/300.
Các biến thể SAFE/UNSAFE, corner và outside cũng khớp tỉ lệ thắng đã ghi.
Điểm mật độ 10 mìn là 474/500; baseline 1.000 ván là 961/1.000.
Thời gian mới được đo trên máy cloud và thay thế thời gian laptop lịch sử
trong bản báo cáo cập nhật; không yêu cầu hai môi trường khớp thời gian.

## Các bộ smoke

| Thư mục | Vai trò | Dòng CSV |
|---|---|---:|
| smoke_before_review | Kiểm tra triển khai cũ, trước sửa quy trình | 215 |
| smoke_verified_01 | all sau sửa, 5 ván/cấu hình; bảng và hình | 215 |
| smoke_verified_02 | main lặp lại, 5 ván/cấu hình | 80 |

Smoke chỉ kiểm tra đường đi của quy trình; không gộp vào bộ chính thức.
Lần smoke từ cwd khác và lần chạy source snapshot được lưu ở /tmp trong
phiên xác minh; kết quả so sánh được ghi trong validation.json của bộ đầy đủ.

Báo cáo Word được cập nhật riêng, có audit đối chiếu bảng/hình. Nội dung
DOCX đã được kiểm tra nhưng chưa dàn trang bằng Word; cần cập nhật mục lục
và số trang khi mở. Không khẳng định bản mới vẫn là 25 trang.
