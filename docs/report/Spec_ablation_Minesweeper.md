# Spec bổ sung ablation cho Minesweeper AI

## 1. Mục tiêu và phạm vi

Đo riêng ảnh hưởng của Degree Heuristic, constraint propagation và INFO trong LV3.

Quy trình tái lập thực nghiệm đã được triển khai theo thông tin của người dùng. Trước khi sửa, đọc code hiện tại và spec tái lập để tích hợp vào các script, CSV và manifest đang có; không triển khai lại hoặc ghi đè phần đã hoàn thành.

- Degree và propagation: đánh giá chi phí DFS trên cùng trạng thái frontier, giữ nguyên tập nghiệm và xác suất.
- INFO: đánh giá lựa chọn nước đoán và kết quả toàn ván.
- Giữ mặc định hiện tại của solver và các cấu hình mở đầu/ngoài frontier đã triển khai.
- Không thêm cache, timeout, xấp xỉ, thay đổi luật sinh bàn hoặc thay đổi cách đếm guesses trong đợt này.
- Không sửa số liệu trong báo cáo trước khi có kết quả thực nghiệm mới.

## 2. Các biến thể

| ID | Chọn biến DFS | Propagation | Phá hòa khi đoán |
|---|---|---|---|
| `baseline` | Degree | Bật | INFO, rồi tọa độ |
| `no_degree` | Tọa độ nhỏ nhất | Bật | INFO, rồi tọa độ |
| `no_propagation` | Degree | Tắt tự gán bắt buộc | INFO, rồi tọa độ |
| `no_info` | Degree | Bật | Tọa độ nhỏ nhất |

Mỗi biến thể chỉ thay đổi một yếu tố so với baseline. Cả bốn giữ nguyên thứ tự thử giá trị 0 rồi 1, phân rã component, trọng số tổng số mìn, tập ứng viên và quy tắc xử lý nước chắc chắn.

Trong spec này, `no_propagation` vẫn giữ pruning bằng kiểm tra tính khả thi; không phải brute-force không cắt nhánh. Phải ghi rõ điều này trong bảng và báo cáo.

## 3. Cấu hình solver

Thêm các lựa chọn keyword hoặc cấu hình tương đương vào LV3:

```python
variable_order = "degree"       # "degree" hoặc "coordinate"
use_propagation = True
guess_tiebreak = "info"         # "info" hoặc "coordinate"
collect_stats = False
```

- Tương thích với constructor, CLI và các lời gọi cũ.
- Các hàm `_solve_component`, `_propagate`, `_choose_move` có thể nhận thêm keyword mặc định để giữ API hiện có; không bắt buộc chuyển classmethod thành instance method.
- Không dùng monkey-patch, thay đổi biến toàn cục hoặc sửa file solver giữa các lần chạy.
- Ghi cấu hình thực tế vào manifest và dữ liệu. Không chỉ ghi solver là `lv3`.

### Khi tắt Degree

Chọn ô chưa gán có tọa độ `(row, col)` nhỏ nhất. Không tính bảng score Degree nếu không dùng nó.

### Khi tắt propagation

Ở mỗi node, chỉ kiểm tra tất cả ràng buộc và không tự gán thêm biến. Với mỗi ràng buộc:

```text
a = tổng giá trị các biến đã gán
u = số biến chưa gán
r = số mìn yêu cầu - a
nếu r < 0 hoặc r > u: cắt nhánh
```

Khi mọi biến đã gán, phải kiểm tra mọi ràng buộc được thỏa chính xác trước khi lưu nghiệm. Không gọi propagation rồi bỏ qua kết quả, vì trạng thái đã bị thay đổi.

### Khi tắt INFO

- Chỉ thay đổi phá hòa giữa các nước đoán có cùng xác suất mìn nhỏ nhất.
- Baseline: xác suất tăng dần, INFO giảm dần, tọa độ tăng dần.
- `no_info`: xác suất tăng dần, tọa độ tăng dần.
- Giữ nguyên lựa chọn giữa các ô có P=0/P=1; không dùng INFO ở bước chọn nước chắc chắn nếu code hiện tại không dùng.
- Tiếp tục tính/ghi INFO nếu cần log; chỉ bỏ vai trò chọn nước đi của nó.

## 4. DFSStats

Thêm dataclass hoặc cấu trúc tương đương, thu thập khi `collect_stats=True`.

| Trường | Định nghĩa |
|---|---|
| `nodes_visited` | Mỗi lần vào SEARCH, gồm root, node bị cắt và node nghiệm, tính một lần. |
| `branch_points` | Số node thực sự chọn biến và tạo hai nhánh 0/1. |
| `pruned_nodes` | Số node bị loại do kiểm tra mâu thuẫn; mỗi node tính một lần. |
| `forced_assignments` | Số biến chưa gán được propagation gán; không gồm phép gán khi phân nhánh. |
| `constraint_checks` | Số lần xét một ràng buộc để kiểm tra/lan truyền, gồm các lượt lặp. |
| `propagation_passes` | Số lượt quét ràng buộc trong propagation, gồm lượt cuối không đổi. |
| `max_depth` | Độ sâu đệ quy SEARCH; root=0, mỗi lần phân nhánh tăng 1; tự gán không tăng độ sâu. |
| `solutions_count` | Tổng số nghiệm component đã lưu. |
| `dfs_time_ms` | Thời gian liệt kê nghiệm component, đo bằng perf_counter_ns. |

- Mỗi component có stats riêng. Stats một nước cộng các bộ đếm/thời gian, lấy max cho `max_depth` và ghi thêm số component, số biến component lớn nhất.
- Reset stats ở đầu mỗi `next_move`; nước do LV1/LV2 trả về có bộ đếm DFS bằng 0, không mang stats của nước trước.
- `no_propagation` có `forced_assignments=0`, `propagation_passes=0`, nhưng vẫn có `constraint_checks`.
- Ghi riêng `probability_time_ms` cho bước kết hợp nghiệm/tính xác suất. Thời gian DFS không gồm bước này, ghi file hoặc vẽ hình.
- Thời gian toàn ván tiếp tục dùng chỉ số batch hiện có. Không cộng nhầm các khoảng đo lồng nhau.
- Khi tắt thống kê, không lưu trace từng node hoặc thêm overhead đáng kể. Khi benchmark, mọi biến thể dùng cùng chế độ thu thập stats.

## 5. Hai loại thí nghiệm

### 5.1 Replay frontier để đo Degree và propagation

Tạo hoặc mở rộng script thu thập snapshot và chạy ablation, đặt trong `docs/report/scripts/`. Có thể dùng hai file `collect_frontiers.py`, `run_ablation.py` hoặc tích hợp hợp lý vào script hiện có.

1. Chạy baseline trên các seed cố định.
2. Chỉ lưu trạng thái khi LV1/LV2 đã bế tắc và LV3 chuẩn bị xử lý ràng buộc bằng DFS.
3. Replay cùng snapshot cho `baseline`, `no_degree`, `no_propagation`.
4. Replay chỉ tính tập nghiệm/xác suất; không áp dụng nước đi để phát triển ba chuỗi trạng thái khác nhau.
5. Chạy `no_info` trên snapshot có thể dùng để ghi thay đổi nước chọn, nhưng hiệu quả thắng toàn ván phải đo bằng thí nghiệm 5.2.

Snapshot JSONL phải đủ để dựng lại PlayerView và đầu vào tính xác suất: kích thước, tổng số mìn, ô số đã mở, cờ, trạng thái ô ẩn và các trường PlayerView thực tế cần. Ghi kèm seed, bước, cấu hình và phiên bản schema. Không cung cấp vị trí mìn thật cho solver replay.

- Mỗi snapshot có ID/hash từ biểu diễn chuẩn hóa của toàn bộ đầu vào liên quan, không chỉ một component.
- Nếu loại snapshot trùng, lưu danh sách lần xuất hiện và ghi rõ bảng tính trên trạng thái duy nhất hay theo số lần xuất hiện; không âm thầm đổi trọng số mẫu.
- Bảo toàn các ràng buộc gốc, kể cả ràng buộc trùng nếu code hiện tại giữ chúng, vì chúng ảnh hưởng Degree/INFO.
- Với mỗi snapshot, so sánh chính xác tập nghiệm của từng component và xác suất Fraction theo từng ô. Lệch kết quả phải báo lỗi, không tiếp tục xuất kết luận hiệu năng cho lần chạy đó.
- Có thể chuẩn hóa mỗi nghiệm thành tuple 0/1 theo thứ tự tọa độ. So sánh tập nghiệm, không so sánh thứ tự liệt kê hoặc chỉ số lượng nghiệm.
- Với snapshot có tổng trọng số bằng 0/không có nghiệm, so sánh trạng thái bất khả thi và ghi riêng; không tính chúng như trường hợp xác suất bình thường.

### 5.2 Chạy toàn ván để đo INFO

Chạy `baseline` và `no_info` trên cùng cấu hình, cùng seed, cùng vị trí mở đầu và tập ứng viên. Giữ nguyên code sinh bàn; có thể lưu fingerprint bàn sau lần mở đầu để xác nhận hai biến thể thực sự bắt đầu từ cùng bàn.

Ghi kết quả từng seed: thắng/thua/bế tắc, moves, guesses, time_ms và tổng DFSStats. Các chuỗi nước đi có thể khác sau khi phá hòa; không dùng so sánh node toàn ván này để khẳng định riêng hiệu quả Degree/propagation.

### Cỡ mẫu

- Chạy thử trước trên beginner với 10 ván để kiểm tra pipeline và có snapshot thực sự gọi DFS; nếu không có, bổ sung seed hoặc fixture xác định.
- Lần đo chính: beginner 1.000 ván, intermediate 1.000 ván, expert 300 ván; seed bắt đầu 0. Các giá trị có thể cấu hình, phải ghi cỡ mẫu thực tế.
- Thu thập frontier từ baseline cùng các cấu hình trên. Replay số trạng thái thu được, không tuyên bố số snapshot bằng số ván.
- Với đo thời gian replay: một lượt warm-up không ghi kết quả; 5 lượt đo cho mỗi snapshot/biến thể, dùng trung vị. Xáo trộn thứ tự biến thể bằng seed cố định; chạy tuần tự trên cùng máy.
- Bộ đếm cấu trúc ghi một lần, không nhân lên theo số lượt đo. Mọi lượt replay phải cho kết quả nhất quán.
- Không đặt timeout riêng cho một biến thể. Nếu một snapshot không chạy hết, ghi incomplete và loại cả bộ so sánh cặp của snapshot đó khỏi bảng hoàn tất, đồng thời báo số lượng bị loại.

## 6. Dữ liệu và tổng hợp

Tích hợp vào cấu trúc thư mục lần chạy và manifest đã có. Không ghi đè dữ liệu baseline cũ.

Đầu ra tối thiểu:

- `frontiers.jsonl`: đầu vào replay và nguồn gốc từng trạng thái.
- `ablation_frontiers.csv`: một dòng cho mỗi snapshot/biến thể, kèm stats, số lượt đo, trung vị thời gian và trạng thái đối chiếu nghiệm/xác suất.
- `ablation_games.csv`: một dòng mỗi cấu hình/seed/biến thể cho thí nghiệm toàn ván.
- `ablation_summary.csv`, `ablation_tables.md`: các bảng cho báo cáo.
- Manifest: commit, cấu hình ablation, môi trường, seed, phương pháp đo và trạng thái hoàn tất; dùng lại quy tắc provenance của pipeline hiện có.

Bảng replay gồm số snapshot, node trung bình/trung vị/P95, nhánh bị cắt, forced assignments, thời gian DFS trung vị/P95 và số ca đối chiếu đúng.

- Tính thêm tỷ lệ tổng node biến thể / tổng node baseline trên cùng tập snapshot và tỷ lệ thời gian tương ứng. Ghi rõ đây là tỷ lệ tổng, không phải trung bình tỷ lệ từng snapshot.
- Báo cả chi phí thấp hơn lẫn cao hơn; không yêu cầu Degree/propagation phải cải thiện mọi trường hợp.
- Không dùng số node giảm để suy ra thời gian chắc chắn giảm: propagation có chi phí riêng.

Bảng INFO gồm thắng/thua/bế tắc, Wilson 95%, guesses và moves trung bình cho từng cấu hình.

- Ghép theo seed để ghi b: baseline thắng, no_info không thắng; c: no_info thắng, baseline không thắng.
- Có thể tính McNemar exact cho kết quả thắng/không thắng bằng kiểm định nhị thức hai phía trên b+c, p0=0.5; nếu b+c=0 thì p=1. Ghi rõ phương pháp và mọi phụ thuộc được thêm.
- Chênh lệch tỉ lệ thắng tính theo điểm phần trăm. Wilson của từng biến thể không phải khoảng tin cậy cho chênh lệch.
- Không kết luận hai biến thể tương đương chỉ vì kiểm định không phát hiện chênh lệch.
- Nếu bế tắc xuất phát từ lỗi thực thi hoặc dữ liệu không hoàn tất, báo riêng và xử lý lỗi trước khi dùng bảng để kết luận hiệu quả chiến lược.

Biểu đồ tùy chọn: node/thời gian replay theo biến thể; tỉ lệ thắng baseline/no_info theo preset. Mọi hình đọc dữ liệu đầu ra, không viết cứng số liệu.

## 7. Kiểm tra tính đúng

- Mọi cấu hình mặc định giữ nguyên nước đi và kết quả của code trước khi thêm ablation; bật stats không làm thay đổi hành vi.
- `baseline`, `no_degree`, `no_propagation` cho cùng tập nghiệm và xác suất trên các fixture nhỏ và snapshot replay.
- Có fixture propagation tự gán được biến, fixture có nhánh mâu thuẫn và fixture không có nghiệm; kiểm tra định nghĩa các bộ đếm.
- Có fixture hai ô cùng P nhỏ nhất nhưng INFO khác: baseline chọn theo INFO, no_info chọn theo tọa độ; nước chắc chắn không bị đổi bởi cấu hình INFO.
- Stats được reset đúng giữa hai nước, kể cả nước tiếp theo do LV1 giải.
- Có thể dùng brute-force độc lập trên component nhỏ để tăng độ tin cậy: thử mọi gán 0/1 và kiểm tra tổng trực tiếp, không gọi lại propagation của DFS. Đây là kiểm chứng bổ trợ, không thay thế thí nghiệm ablation.
- Không kiểm thử theo số milliseconds cố định; kiểm tra thời gian không âm và dữ liệu được ghi đúng.
- Chạy các kiểm thử hiện có và các kiểm thử mới phù hợp trước khi chạy benchmark chính.

## 8. Tài liệu và nghiệm thu

README cập nhật lệnh thu thập/replay/chạy toàn ván/tổng hợp, ý nghĩa từng bộ đếm, định nghĩa no_propagation và cấu hình từng biến thể. Cung cấp một lệnh chạy thử ít ván và lệnh chạy đủ bộ.

Hoàn tất khi:

1. Ba lựa chọn ablation có thể cấu hình mà không sửa tay solver.
2. DFSStats có định nghĩa rõ, không đổi hành vi mặc định và không cộng dồn sai.
3. Replay trên cùng đầu vào chứng minh các biến thể tìm kiếm giữ nguyên nghiệm/xác suất.
4. Thí nghiệm INFO ghép được từng seed và lưu đủ dữ liệu để kiểm tra lại.
5. Bảng, hình và kết luận đều được tạo từ dữ liệu thực tế; số ca không hoàn tất được báo rõ.
6. Báo cáo có thể bổ sung một mục Ablation trong Chương 4: Degree/propagation đánh giá hiệu năng tìm kiếm; INFO đánh giá lựa chọn nước đi. Chỉ cập nhật nhận xét và kết luận sau khi có kết quả.
