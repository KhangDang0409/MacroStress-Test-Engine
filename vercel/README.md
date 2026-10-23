# MacroStress Test — bản chuyển sang Vercel

Bộ này chuyển đúng file app.py (MacroStress Test) bạn đã gửi. Không bao gồm VN Market Support Screener.

## 1. Những gì được giữ nguyên

`original_streamlit.py` là bản sao nguyên byte của file bạn gửi. Không viết lại công thức sang JavaScript. `bridge.py` cung cấp lớp thay thế các lệnh giao diện Streamlit; Python vẫn thực thi nguyên chương trình gốc. `app.py` nhận input từ website và trả kết quả JSON. Biểu đồ vẫn được dựng bằng Plotly Python của bản gốc, rồi chuyển nguyên dữ liệu/layout sang Plotly.js.

Giữ nguyên:
- Danh sách ticker tự nhập, chuẩn hóa chữ hoa, trọng số tự chuẩn hóa bằng tổng; không tự cấm trọng số âm vốn được bản gốc cho phép.
- Giá trị mặc định, cả bốn kịch bản và mọi hệ số.
- Tải dữ liệu 2 năm bằng yfinance; dropna/fillna và cách tính volatility, correlation, drift, ADTV.
- Phân loại relative risk, cutoff volatility 0.25, clipping, cách chọn benchmark theo ticker đầu tiên, fallback SPY 0.15.
- Correlation stress, Cholesky và nhánh sửa eigenvalue.
- Toàn bộ cấp phát mảng, thứ tự random.normal/random.poisson, nhân jump count với jump size và vòng lặp mô phỏng.
- Liquidity penalty, weighted portfolio paths, percentile 5%, conditional tail mean, probability of loss.
- Bốn ô chỉ số; bảng phân loại; 100 đường mẫu và đường vốn ban đầu; histogram nbins=60 và đường đánh dấu; hai correlation heatmaps.
- 30–252 ngày, 1.000–10.000 đường; không âm thầm hạ mức tính toán, thay dữ liệu hay dùng kết quả mẫu.
- Tự chạy khi mở trang, cập nhật khi thay đổi input; thêm nút Run simulation để chạy lại thủ công.

Các khác biệt về hạ tầng/giao diện được công khai:
- HTML/CSS thay giao diện Streamlit. Màu và cách bố trí không giống từng pixel.
- Cache thị trường TTL 300 giây và cache mô phỏng theo đối số được tái hiện bằng file trong /tmp. Cache giới hạn 128 MiB, có thể bị thu hồi; không chia sẻ giữa các instance Vercel. Cache của Streamlit cũng không được chuyển sang hosting mới. Cache miss sẽ chạy lại đúng thuật toán gốc với các số ngẫu nhiên mới.
- Thêm kiểm tra input sai, báo lỗi HTTP và chống hai request cùng instance xen kẽ random state. Request đồng thời có thể nhận 429 để thử lại.
- Đổi vị trí cache nội bộ yfinance sang /tmp để dùng được trong hệ thống chỉ đọc của serverless.
- Không sửa ý nghĩa nhãn VaR/CVaR hay các nhận định trong phần giới thiệu; chúng được giữ theo code gốc. Việc bảo toàn không đồng nghĩa xác nhận mô hình tài chính đúng về lý thuyết.

## 2. Hiểu đúng về kết quả giống bản gốc

Bản gốc không đặt seed. Hai lần chạy mới có thể cho kết quả khác nhau. Dữ liệu Yahoo cũng thay đổi; thư viện NumPy/BLAS/yfinance khác phiên bản có thể ảnh hưởng kết quả.

Đã kiểm tra bằng cùng dữ liệu cố định, cùng random seed và cùng môi trường: các đường mô phỏng, số liệu và JSON của biểu đồ khớp tuyệt đối (không dùng tolerance để làm tròn sai lệch). Xem VERIFICATION.md. Seed chỉ dùng trong test, không bị thêm vào thuật toán chạy thật.

Không cam kết một lần chạy trên Vercel sẽ có cùng con số với một lần chạy độc lập trên Streamlit. Muốn đối chiếu tuyệt đối hai môi trường cần cùng dữ liệu đầu vào, cùng phiên bản thư viện/nền tảng số học, cùng trạng thái random và trạng thái cache. Chưa có requirements/lockfile của deployment Streamlit cũ để xác nhận phiên bản của nó.

## 3. Cách deploy dễ nhất: GitHub → Vercel

### Bước 1 — Giải nén

Giải nén `macrostress-vercel.zip` bằng Extract All trên Windows. Mở thư mục `macrostress-vercel` bên trong. Bạn phải thấy trực tiếp:

- app.py
- bridge.py
- original_streamlit.py
- requirements.txt
- vercel.json
- .python-version
- public/ (index.html, client.js, style.css, plotly.min.js)
- tests/, README.md, VERIFICATION.md, SOURCE_SHA256.txt và các file cấu hình khác.

Không tải riêng app.py lên Vercel và không dùng app.py Streamlit cũ làm entrypoint. Bản gốc đã nằm trong original_streamlit.py.

### Bước 2 — Tạo repository GitHub mới

1. Đăng nhập https://github.com.
2. Chọn New repository; đặt tên `macrostress-vercel`.
3. Chọn tài khoản cá nhân làm owner; Public hoặc Private đều được.
4. Create repository.
5. Chọn Upload an existing file (hoặc Add file → Upload files nếu repo đã có README).
6. Kéo toàn bộ NỘI DUNG bên trong thư mục macrostress-vercel lên trang upload. Giữ nguyên public/ và tests/ là thư mục.
7. Commit changes.
8. Kiểm tra tại trang chính repo: app.py, requirements.txt và vercel.json phải nằm ngay ở gốc; public/index.html phải truy cập được. Đừng chỉ upload ZIP.
9. Kiểm tra có `.python-version` với nội dung `3.12`. Nếu thiếu khi kéo thả, dùng Add file → Create new file để tạo file đó. Các file chấm khác chủ yếu hỗ trợ loại bỏ thư mục tạm.

### Bước 3 — Import trên Vercel

1. Vào https://vercel.com, đăng nhập bằng GitHub.
2. Chọn workspace cá nhân, gói Hobby (free). Không cần mua Pro để thử bộ này.
3. Add New → Project.
4. Cho Vercel quyền truy cập đúng repository rồi bấm Import cạnh macrostress-vercel.
5. Project Name: `macrostress-vercel` hoặc tên còn trống.
6. Framework Preset: **Flask**. Vercel có thể tự nhận diện từ requirements.txt.
7. Root Directory: gốc repo (`./`). Nếu bạn đã upload nguyên một folder bọc bên ngoài, chọn chính folder chứa app.py làm Root Directory.
8. Giữ mặc định các ô Build Command, Output Directory và Install Command; không điền `streamlit run`, `npm run build` hoặc `dist`.
9. Chưa cần environment variable hay API key cho code này.
10. Bấm Deploy và đợi trạng thái Ready. requirements.txt pin các dependency chính; Flask/Python được Vercel cài tự động.

### Bước 4 — Kiểm tra sau deploy

1. Bấm Visit để mở URL production do Vercel cấp.
2. Thử URL `/api/health` trên chính domain đó: phải trả JSON status="ok".
3. Mở trang chính: giữ JNJ, WMT, PG; đợi dữ liệu và kết quả xuất hiện.
4. Kiểm tra bốn metric, mở bảng Risk Classification, bấm đủ ba tab.
5. Chọn lần lượt ba kịch bản stress, xác nhận mỗi lần có kết quả hoặc thông báo lỗi rõ ràng.
6. Đổi trọng số, ngày và số đường; không so hai lần chạy khác seed bằng cách đòi mọi con số bằng nhau.
7. Mở URL production bằng cửa sổ ẩn danh. Nếu bị yêu cầu đăng nhập Vercel, kiểm tra Settings → Deployment Protection và phạm vi áp dụng; dùng domain production công khai phù hợp cho CV, không dùng preview đang được bảo vệ.
8. Sau khi kiểm tra, thay link trong CV bằng URL production mới. Không cần mua domain riêng.

### Bước 5 — Các lần cập nhật sau

Sửa file trong repo rồi Commit. Repository đã liên kết sẽ tạo deployment mới. Kiểm tra deployment mới Ready và chạy thử trước khi dùng. Khi sửa thuật toán gốc sau này, SOURCE_SHA256.txt và test integrity cần cập nhật có chủ đích, không tự bỏ test.

## 4. Chạy trên laptop trước khi deploy (không bắt buộc)

Cài Python 3.12. Mở PowerShell tại thư mục có app.py rồi chạy từng dòng:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Mở http://127.0.0.1:5000. Dừng bằng Ctrl+C. Không cần cài Node hoặc dùng streamlit run cho bản web này.

Chạy bộ đối chiếu:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest==8.3.5
.\.venv\Scripts\python.exe -m pytest tests -q
```

## 5. Lỗi thường gặp

| Hiện tượng | Cách kiểm tra |
|---|---|
| Vercel không nhận Flask | Kiểm tra app.py và requirements.txt ở Root Directory; chọn Flask, không chọn Vite/Next.js. |
| ModuleNotFoundError hoặc build failed | Mở Build Logs; kiểm tra toàn bộ file đã upload, Python 3.12 và dependency cài thành công. |
| Trang chính 404 | Kiểm tra public/index.html và Root Directory. |
| Biểu đồ không tải | Kiểm tra public/plotly.min.js, public/client.js; mở Console/Network của trình duyệt. Thư viện biểu đồ đã kèm trong ZIP, không dùng CDN ngoài. |
| API Cloud Blocked / dữ liệu thiếu | Đây là thông báo gốc của app khi tải thiếu dữ liệu; chưa đủ để kết luận nguyên nhân. Kiểm tra ticker, thử lại, xem Runtime Logs. Yahoo có thể từ chối/rate-limit IP cloud. |
| FUNCTION_INVOCATION_TIMEOUT / 504 | Một request vượt 300 giây. Kiểm tra thời gian tải dữ liệu và mô phỏng trong logs; không có kết quả xấp xỉ thay thế. |
| Hết RAM / process killed | Cấu hình nhiều ticker × nhiều đường × nhiều ngày vượt RAM. Chọn cấu hình nhẹ hơn khi sử dụng hoặc đổi tài nguyên hosting. Code không tự giảm số đường. |
| HTTP 429 | Một mô phỏng khác đang chạy trên cùng instance. Đợi hoàn tất rồi thử lại. |
| Kết quả khác Streamlit | So sánh đúng dữ liệu, dependency, seed và cache; sự khác biệt giữa các lần Monte Carlo không tự chứng minh lỗi chuyển đổi. |
| Trang yêu cầu đăng nhập Vercel | Kiểm tra domain production và Deployment Protection. |

## 6. Giới hạn miễn phí và trạng thái xác minh

Tài liệu Vercel được kiểm tra ngày 23/10/2026: Hobby Functions có tối đa 300 giây/request và 2 GB RAM; payload request/response tối đa 4.5 MB; Python bundle tiêu chuẩn 500 MB. Hạn mức tháng vẫn áp dụng. Xem nguồn chính thức trước khi triển khai vì chính sách có thể thay đổi.

Không thể bảo đảm mọi số lượng ticker tùy ý ở 10.000 đường × 252 ngày đều nằm trong 2 GB. Chỉ riêng bốn mảng lớn của code gốc dùng xấp xỉ 32 × days × tickers × paths byte (chưa kể các mảng và thư viện khác). Giữ nguyên code đồng nghĩa giữ nguyên đặc tính sử dụng RAM này. Không tự cắt ticker, giảm precision hoặc bỏ mảng.

Chuyển hosting giải quyết việc phải đánh thức Streamlit Community Cloud, nhưng request đầu vẫn có thể có cold start; không có lời hứa uptime tuyệt đối. Hosting mới cũng không bảo đảm Yahoo Finance luôn chấp nhận request.

Chưa deploy vào tài khoản Vercel của bạn; vì vậy chưa xác nhận build, quota và khả năng truy cập Yahoo từ chính IP Vercel của bạn. Xem kết quả kiểm tra thực tế trong VERIFICATION.md.

Nguồn:
- https://vercel.com/docs/frameworks/backend/flask
- https://vercel.com/docs/functions/runtimes/python
- https://vercel.com/docs/functions/limitations
- https://vercel.com/docs/plans/hobby
