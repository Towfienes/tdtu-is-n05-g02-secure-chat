# Kịch bản demo Secure Android Chat

Thời lượng dự kiến khoảng 6 phút. Mở sẵn hai app **Secure Chat Baseline** và **Secure Chat Pinned** trên emulator API 36, cùng terminal ở thư mục dự án. Làm theo lệnh cài đặt và ADB reverse trong README. Các bước sau dùng cùng một cổng 8443 và chỉ đổi fixture TLS của backend.

| Thời gian | Thao tác và lời nói |
| --- | --- |
| 00:00–00:45 | Giới thiệu lớp N05, nhóm G02 và Topic 13. “Giữa kỳ nhóm phân tích quyền ứng dụng, Intent và lưu trữ trên Android. Hôm nay nhóm chạy app chat thật để kiểm tra những ranh giới đó. Phần chính là ứng dụng xác thực máy chủ qua TLS.” |
| 00:45–01:45 | Chạy backend fixture A, bấm **Refresh** lần lượt ở Baseline và Pinned. “Hai bản dùng cùng địa chỉ, cùng CA và cùng kiểm tra hostname. Bản Pinned còn kiểm tra hash của khóa công khai. A là khóa chính đã pin nên cả hai kết nối được.” |
| 01:45–03:00 | Dừng backend A, chạy B. Baseline **Refresh** thành công. Trong Pinned, nhập một dòng mẫu rồi bấm **Send message**. “B có chứng thư hợp lệ với cùng CA và hostname, nhưng khác khóa. Bản Pinned từ chối trong bắt tay TLS. Log backend không có POST từ lượt Pinned, và Logcat ghi lỗi pin.” |
| 03:00–03:50 | Chạy lại A. Gửi một dòng mẫu trong Pinned rồi mở chi tiết bằng cách bấm vào tin nhắn. “Đổi về đúng khóa thì gửi và xem lại được. Lượt gửi chỉ cần một POST vì server trả luôn hội thoại đã cập nhật. Bản Baseline có thể đọc và trả lời trên cùng server. Chi tiết tin nhắn chỉ được mở bên trong ứng dụng bằng Intent tường minh. Android từ chối yêu cầu từ UID bên ngoài, như kết quả kiểm thử đi kèm.” |
| 03:50–04:50 | Tắt backend và force-stop app Pinned, mở lại. “Tin nhắn đã gửi vẫn đọc được từ cache. AES-GCM bảo vệ nội dung và phát hiện sửa đổi. Khi kiểm thử lật một byte của dữ liệu mã hóa, phép giải mã báo lỗi xác thực. Khóa nằm trong Android Keystore.” |
| 04:50–05:45 | Chốt bằng bảng kết quả và hai hạn chế. “Pin dự phòng đã kiểm tra để hỗ trợ chuyển khóa. Quản lý vòng đời khóa rất quan trọng. Mô hình chat chỉ chạy nội bộ với dữ liệu mẫu và không có hệ thống tài khoản. Cache mã hóa không bảo vệ được nội dung đang mở trong tiến trình đã bị kiểm soát.” |

Nếu emulator mất kết nối giữa buổi, dùng hình trong phần Walkthrough và log đối chiếu theo từng fixture để giải thích các lượt đã chạy. Các tệp đó được ghi từ lần chạy Android thực tế.
