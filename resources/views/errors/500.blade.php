@extends('errors::layout')
@section('title', 'Có lỗi xảy ra')
@section('code', '500')
@section('heading', 'App gặp lỗi khi xử lý')
@section('message', 'Có gì đó trục trặc ở phía máy chủ. Anh thử tải lại sau ít giây; nếu vẫn lỗi, xem nhật ký trong thư mục dữ liệu của app.')
@section('extra')
    <a class="btn" href="javascript:location.reload()">Tải lại</a>
@endsection
