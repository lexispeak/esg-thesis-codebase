from esg_pipeline.ingestion.html_helpers import parse_links_from_html

SAMPLE_HTML = '''
<div id="document-content" class="document-content"><div class="row"><div class="col-sm-8 col-md-6"><div class="auto-resize"><div class="list-group m-b"><a class="radio list-group-item bg active no-m-t"><span>Loại tài liệu</span></a><a class="radio list-group-item"><label><input type="radio" value="0" checked=""><span>Tất cả</span></label></a></div></div></div><div class="col-sm-16 col-md-18"><div class="headline bb3 red"><h4 class="title al-middle">Kỳ báo cáo</h4></div><div class="p-t-xs"><p class="i-b-d bg-hover-yellow"><a class="doc__ttl--text-link text-link" href="https://static2.vietstock.vn/data/HOSE/2025/NGHI QUYET HDQT/VN/20251105___tpb___cbtt_nq_hdqt_vv_ket_qua_dot_phat_hanh_co_phieu_de_tra_co_tuc_signed.pdf" data-id="524449" data-lastupdate="/Date(1762479979797)/" title="Nghị quyết HĐQT về việc thông qua kết quả đợt phát hành cổ phiếu để trả cổ tức" target="_blank" rel="noopener noreferrer"><span class="doc__ttl-file-name"> <i class="fa-regular fa-file-pdf fz"></i> Nghị quyết HĐQT về việc thông qua kết quả đợt phát hành cổ phiếu để trả cổ tức</span><span class="doc__ttl--lastupdate" title="Ngày cập nhật">07/11/2025 08:46</span></a></p>
<p class="i-b-d bg-hover-yellow active"><a class="doc__ttl--text-link unzippdf text-link" href="https://static2.vietstock.vn/data/HOSE/2025/KHAC/VN/TPB_DIEULE_2025.zip" data-id="519863" data-lastupdate="/Date(1757900189387)/" title="Điều lệ năm 2025 " target="_blank" rel="noopener noreferrer"><span class="doc__ttl-file-name"> <i class="fa fa-folder-closed text-warning fz"></i> Điều lệ năm 2025 </span><span class="doc__ttl--lastupdate" title="Ngày cập nhật">15/09/2025 08:36</span></a></p>
</div></div></div></div>
'''


def test_parse_links_extracts_static_files():
    links = parse_links_from_html(SAMPLE_HTML)
    urls = [l['url'] for l in links]
    titles = [l['title'] for l in links]
    dates = [l['posted_date_raw'] for l in links]

    assert any('TPB_DIEULE_2025.zip' in u for u in urls), 'zip link not found'
    assert any('cbtt_nq_hdqt_vv_ket_qua_dot_phat_hanh' in u for u in urls), 'pdf link not found'
    assert any('Nghị quyết HĐQT về việc thông qua kết quả đợt phát hành' in t for t in titles), 'pdf title not captured'
    assert any('15/09/2025' in (d or '') or '07/11/2025' in (d or '') for d in dates), 'dates not captured'
