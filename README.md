# Công việc giảng viên

Ứng dụng quản lý phân công công việc giảng viên dùng trong nội bộ cơ quan. Giao diện tiếng Việt, chạy bằng **Python 3.10 trở lên**, không cần cài thêm thư viện, không cần Node.js và không dùng dịch vụ bên ngoài.

## Chạy trong VS Code

1. Giải nén project. Mở thư mục `giang-vien-workspace` bằng **File → Open Folder** hoặc mở `giang-vien.code-workspace`.
2. Mở **Terminal → New Terminal**.
3. Chạy trên macOS / Linux:

   ```sh
   python3 server.py
   ```

   Trên Windows:

   ```powershell
   py -3 server.py
   ```

4. Mở **http://localhost:8000** trong trình duyệt.
5. Lần đầu: tạo tài khoản quản trị với mật khẩu ít nhất 10 ký tự. Có thể bật dữ liệu mẫu để trải nghiệm hoặc bỏ chọn để bắt đầu với dữ liệu thật.

Cũng có thể chọn **Terminal → Run Task** và chọn tác vụ phù hợp hệ điều hành. Nếu đã cài Python extension của VS Code, nhấn **F5** với cấu hình “Chạy ứng dụng giảng viên”. Nếu cổng 8000 đã được dùng, chạy `python3 server.py --port 8001` rồi mở địa chỉ tương ứng. Nhấn **Ctrl+C** để dừng.

## Hai trang chính

Công việc mới luôn bắt đầu ở trạng thái **Chưa hoàn thành**. Biểu mẫu thêm mới hiển thị trạng thái cố định; chỉ có thể đổi sang hoàn thành sau khi tạo, bằng thao tác cập nhật hoặc đánh dấu hoàn thành. Máy chủ áp dụng quy tắc này cho cả quản trị và lãnh đạo.

- **Công việc**: STT, tên việc, giảng viên phụ trách chính, lãnh đạo phân công, thời hạn, trạng thái. Thêm / sửa / xóa có xác nhận; đánh dấu hoàn thành hoặc mở lại; xem ghi chú; tìm theo tên việc / giảng viên / lãnh đạo (hỗ trợ tìm không dấu); lọc theo người phụ trách, lãnh đạo, trạng thái, quá hạn; sắp xếp và phân trang; xuất danh sách theo bộ lọc thành CSV mở được bằng Excel.
- **Dashboard / Khối lượng công việc**: mọi tài khoản cùng thấy tên giảng viên và số việc chưa hoàn thành của từng người, gồm cả người có 0 việc. Không hiển thị tên việc, ghi chú, thời hạn hoặc lãnh đạo phân công, không có liên kết mở việc của người khác. Hiển thị thêm tổng số việc chưa xong, trung bình và nhóm ít việc.

**Cách tính**: chưa hoàn thành gồm cả việc quá hạn. Quá hạn = chưa hoàn thành và ngày hạn nhỏ hơn ngày hiện tại của máy chủ; việc đến hạn hôm nay chưa bị tính quá hạn. Tổng = chưa hoàn thành + đã hoàn thành. Giảng viên đang hoạt động chưa có việc vẫn hiện số 0. Người ngừng hoạt động còn việc chưa xong vẫn hiện trên Dashboard; người ngừng hoạt động chỉ còn việc đã xong được giữ trong danh sách và bộ lọc, không hiện trong Dashboard. Khối lượng hiện dựa trên **số lượng**, chưa quy đổi giờ hoặc độ khó. Ngày hệ thống lấy từ máy chủ: đặt múi giờ máy chủ đúng với đơn vị.

## Nhân sự và tài khoản

Quản trị mở **Nhân sự** trên trang Công việc để thêm giảng viên, lãnh đạo hoặc người kiêm hai vai trò. Có thể ngừng hoạt động để giữ lịch sử; không xóa được người đã gắn với công việc.

Tài khoản đăng nhập được quản trị quản lý tại **Tài khoản & quyền** trong menu bên trái. Khi tạo tài khoản giảng viên hoặc lãnh đạo, bắt buộc chọn **Nhân sự liên kết** đúng vai trò. Phạm vi việc được xác định bằng ID nhân sự này, không dựa vào tên hiển thị hoặc lựa chọn trên trình duyệt. Một nhân sự chỉ gắn với một tài khoản.

| Quyền | Xem công việc | Chỉnh sửa | Dashboard chung |
| --- | --- | --- | --- |
| Quản trị viên | Toàn bộ | Thêm/sửa/xóa mọi việc; quản lý nhân sự, tài khoản | Tên và số việc chưa hoàn thành |
| Lãnh đạo | Chỉ việc do chính mình phân công | Thêm/sửa/xóa việc của mình; đổi người phụ trách và thời hạn; tên lãnh đạo được cố định theo tài khoản | Tên và số việc chưa hoàn thành |
| Giảng viên | Chỉ việc được giao cho nhân sự liên kết | Sửa tên việc, ghi chú, trạng thái; không thêm/xóa; không đổi người phụ trách, lãnh đạo hoặc thời hạn | Tên và số việc chưa hoàn thành |
| Chỉ xem việc cá nhân | Chỉ việc của nhân sự liên kết; nếu chưa liên kết thì không có việc | Không được chỉnh sửa | Tên và số việc chưa hoàn thành |

CSV chỉ xuất danh sách mà tài khoản được phép xem. Lãnh đạo chỉ nhận được nội dung việc do mình phân công từ API; chuyển việc sang lãnh đạo khác bằng tài khoản quản trị sẽ thay đổi quyền truy cập ngay ở lần tải dữ liệu tiếp theo. Tài khoản giảng viên không nhận được nội dung việc của người khác từ API, kể cả khi tự đổi bộ lọc hoặc gửi yêu cầu trực tiếp. Chuyển người phụ trách làm thay đổi quyền xem ngay ở lần tải dữ liệu tiếp theo. Dashboard dùng phép đếm tại máy chủ; không tải toàn bộ việc xuống trình duyệt giảng viên để tính thống kê.

Với tài khoản lãnh đạo, cột **Lãnh đạo phân công** tự lấy từ nhân sự gắn với tài khoản đăng nhập khi thêm mới; luôn hiển thị cố định và không thể đổi khi chỉnh sửa. Máy chủ tự xác định người phân công và chặn việc giả mạo lãnh đạo khác. Chỉ quản trị được chọn hoặc chuyển lãnh đạo phân công từ danh sách. Khi giảng viên chỉnh sửa, người phụ trách, lãnh đạo phân công và thời hạn hiển thị trong các ô xám cố định, không có danh sách lựa chọn hoặc nút mở lịch; API vẫn kiểm tra và ngăn mọi thay đổi trái quyền.

Bấm tên tài khoản góc phải để đổi mật khẩu. Khóa tài khoản, đổi quyền hoặc đổi nhân sự liên kết sẽ vô hiệu các phiên của tài khoản đó. Nhân sự bị ngừng hoạt động hoặc bỏ vai trò tương ứng sẽ không đăng nhập được bằng tài khoản giảng viên/lãnh đạo đã gắn. Đổi mật khẩu cá nhân đăng xuất các phiên khác. Quản trị đang đăng nhập không thể tự khóa hoặc hạ quyền. Phạm vi lãnh đạo được giới hạn theo người phân công, chưa chia theo khoa/bộ môn; chưa có khôi phục mật khẩu qua email.

Gói mã nguồn nộp thi không chứa cơ sở dữ liệu, mật khẩu, phiên đăng nhập hoặc danh sách tài khoản đang dùng trên máy cá nhân. Cài mới từ gói này sẽ hiển thị bước tạo tài khoản quản trị đầu tiên. Người chấm tự đặt mật khẩu quản trị, có thể chọn dữ liệu nhân sự và công việc minh họa; sau đó tạo tài khoản giảng viên và lãnh đạo qua giao diện. Không có tài khoản đăng nhập mặc định.

Khi nâng cấp từ bản cũ, ứng dụng tự thêm liên kết tài khoản–nhân sự và cập nhật vai trò trong SQLite, giữ nguyên công việc, ID tài khoản và mật khẩu. Tài khoản lãnh đạo cũ chưa có nhân sự liên kết cần được quản trị gắn đúng lãnh đạo trước khi đăng nhập. Tài khoản “Chỉ xem” cũ chuyển sang phạm vi việc cá nhân; quản trị cần gắn nhân sự nếu muốn cấp quyền xem việc. Luôn sao lưu cơ sở dữ liệu trước nâng cấp.

## Chạy chung trong mạng LAN

Chọn một máy làm máy chủ, giữ ứng dụng chạy trên máy này. Các máy khác dùng trình duyệt truy cập cùng máy chủ để dùng chung dữ liệu.

```sh
python3 server.py --host 0.0.0.0 --port 8000
```

Ví dụ máy chủ có IP nội bộ `192.168.1.20`, máy khác mở `http://192.168.1.20:8000`. Cho phép cổng 8000 qua tường lửa **chỉ với mạng nội bộ**, và không chuyển tiếp cổng ra Internet. Nên dùng IP cố định hoặc tên máy chủ nội bộ. Khi truy cập nhiều máy, không chạy từng bản độc lập vì mỗi bản có một cơ sở dữ liệu riêng.

Ứng dụng dùng máy chủ HTTP tích hợp Python, phù hợp bản triển khai thử nghiệm nội bộ quy mô nhỏ. HTTP không mã hóa mật khẩu và nội dung trên đường truyền. Khi đưa vào vận hành chính thức, nên đặt sau reverse proxy HTTPS (ví dụ Caddy/Nginx), giới hạn mạng truy cập và đặt biến môi trường `COOKIE_SECURE=1` để cookie chỉ đi qua HTTPS. Nếu chỉ dùng localhost hoặc LAN HTTP thì giữ mặc định, không bật biến này. Cần đánh giá tải và quy trình sao lưu của đơn vị trước triển khai rộng. Ứng dụng chưa tích hợp SSO, lịch công tác, tệp đính kèm hay thông báo tự động.

## Lưu dữ liệu và sao lưu

- Dữ liệu bền vững nằm ở `data/workspace.sqlite3`, tự tạo khi chạy lần đầu. Khởi động lại vẫn giữ công việc, nhân sự và tài khoản.
- Cách sao lưu đơn giản: **dừng ứng dụng**, sao chép toàn bộ thư mục `data/` sang nơi lưu trữ được kiểm soát, rồi chạy lại. Không sao chép riêng file SQLite trong khi máy chủ đang ghi dữ liệu.
- Khôi phục: dừng ứng dụng, giữ lại bản `data/` hiện tại để dự phòng, thay bằng thư mục sao lưu, rồi khởi động lại.
- Có thể đặt `WORKSPACE_DB` trỏ đến vị trí cơ sở dữ liệu khác. Không đặt database trên ổ mạng dùng chung; các máy khách truy cập qua trình duyệt.
- Không đưa thư mục `data/` hoặc tệp `TAI-KHOAN-DEMO.txt` vào Git hay gói chia sẻ mã nguồn. `.gitignore` đã cấu hình loại trừ.
- Nếu chọn dữ liệu mẫu, có thể xóa công việc mẫu trước, rồi xóa nhân sự mẫu. Nhãn dữ liệu mẫu được giữ để tránh nhầm nguồn dữ liệu. Cách bắt đầu hoàn toàn mới: dừng ứng dụng, sao lưu rồi đổi tên thư mục `data/` và chạy lại để thiết lập từ đầu.

## Cấu trúc và kiểm tra

```text
server.py             HTTP API, đăng nhập, phân quyền, SQLite
static/index.html     Khung giao diện
static/app.js         Bảng công việc, Dashboard và các biểu mẫu
static/styles.css     Giao diện responsive, tài nguyên cục bộ
tests/test_app.py     Kiểm tra API với cơ sở dữ liệu tạm riêng
.vscode/              Cấu hình chạy và gỡ lỗi trong VS Code
```

Chạy kiểm tra:

```sh
python3 -m unittest discover -s tests -v
```

Kiểm tra dùng cơ sở dữ liệu tạm, không sửa dữ liệu thật. Server kiểm tra quyền ở API, lưu mật khẩu bằng scrypt kèm salt, cookie phiên HttpOnly/SameSite, token CSRF, giới hạn thử sai đăng nhập, kiểm tra đầu vào và chống ghi đè bản công việc cũ. Phiên có hạn 12 giờ. Nhật ký `audit` lưu người thực hiện, loại thao tác và ID bản ghi; chưa có giao diện tra cứu và chưa lưu đầy đủ nội dung trước/sau để phục hồi.


## Giao diện phiên bản 2

Giao diện sử dụng font Be Vietnam Pro được lưu ngay trong `static/fonts/` (giấy phép SIL Open Font License kèm theo). Chữ chính 14px, nút và biểu mẫu 14px; tăng độ tương phản; điều hướng và bảng sử dụng tông xám trung tính với nút hành động xanh dương. Các thông tin phụ dùng 11–13px. Không gọi Google Fonts hay tải tài nguyên từ Internet khi sử dụng ứng dụng.

Bố cục tham khảo nguyên tắc điều hướng nhất quán của [Linear](https://linear.app/changelog/2026-03-12-ui-refresh) và cách sắp xếp bảng công việc của [Asana](https://asana.com/features/project-management/project-views). Đây là giao diện riêng cho yêu cầu quản lý giảng viên.
