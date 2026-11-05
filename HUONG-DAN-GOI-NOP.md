# Hướng dẫn gói mã nguồn nộp sáng kiến

Đơn vị đề xuất dự kiến: Khoa Luật, Học viện An ninh nhân dân.

Gói được chốt từ bản phần mềm chạy cục bộ ngày 31 tháng 10 năm 2026. Đây là bản minh chứng chức năng, chưa phải bản triển khai vận hành chính thức trong mạng Học viện.

## Cài đặt độc lập để đánh giá

1. Giải nén và mở thư mục giang-vien-workspace trong VS Code hoặc Terminal.
2. Cài Python 3.10 trở lên có sqlite3. Với môi trường vận hành thật, dùng phiên bản còn được hỗ trợ và SQLite đã cập nhật các bản sửa hiện hành.
3. Chạy `python3 server.py` trên macOS/Linux hoặc `py -3 server.py` trên Windows.
4. Mở http://localhost:8000, tự tạo tài khoản quản trị đầu tiên. Không sử dụng mật khẩu mặc định.
5. Có thể chọn bộ nhân sự và công việc minh họa khi thiết lập. Các tên và nội dung trong hàm seed_demo là dữ liệu tổng hợp dùng cho minh họa; không phải danh sách nhân sự hay nhiệm vụ thực của Khoa.
6. Tại Nhân sự, tạo hoặc kiểm tra bản ghi giảng viên và lãnh đạo. Tại Tài khoản & quyền, tạo tài khoản và liên kết đúng nhân sự. Tài khoản giảng viên/lãnh đạo phải có liên kết đúng vai trò và đang hoạt động.
7. Tạo công việc bằng tài khoản lãnh đạo: người phân công được cố định theo danh tính đăng nhập; trạng thái ban đầu luôn Chưa hoàn thành. Giảng viên chỉ nhận nội dung việc được giao cho mình. Dashboard chỉ công khai tên và số việc chưa hoàn thành.

## Kiểm tra chức năng

Từ thư mục gốc, chạy `python3 -m unittest discover -s tests -v`. Mã kiểm tra tạo database tạm riêng, dùng thông tin đăng nhập giả định trong test, không dùng dữ liệu thực. Biên nhận kèm theo ghi 35 bài kiểm tra đã đạt trên môi trường máy cá nhân; đây không phải kiểm thử tải hay chứng nhận an toàn thông tin.

## Phạm vi đóng gói

Có mã nguồn Python, HTML, CSS, JavaScript, cấu hình VS Code, bài kiểm tra và font Be Vietnam Pro kèm SIL Open Font License. Không có thư mục data, database, tài khoản/mật khẩu thực, bản sao lưu, ảnh màn hình người dùng, phiên đăng nhập, bộ nhớ đệm hoặc lịch sử Git. MANIFEST_SHA256.txt ghi dấu kiểm tra từng tệp trong gói, không tự bao gồm chính nó.

README.md được điều chỉnh ở đoạn hướng dẫn tài khoản cho phù hợp bản cài sạch; mã nguồn chương trình và các bài kiểm tra được giữ nguyên so với bản chốt.

## Điều kiện trước khi vận hành tại Khoa

Phê duyệt hạ tầng và dữ liệu; nâng môi trường Python/SQLite; thay máy chủ thử nghiệm http.server bằng phương án phục vụ ứng dụng phù hợp; bổ sung HTTPS với chứng thư được các máy nội bộ tin cậy; cấu hình chạy nền, sao lưu và diễn tập khôi phục; kiểm thử quyền, kiểm thử tải và nghiệm thu trên mạng đích. Không mở cổng dịch vụ ra Internet. Không đặt file SQLite trên thư mục chia sẻ mạng.

Quyền sử dụng và phát hành phần mã nguồn sáng kiến do đơn vị/chủ thể có thẩm quyền quyết định. Tệp giấy phép font được giữ nguyên; gói này không tự đặt giấy phép nguồn mở cho mã ứng dụng.
