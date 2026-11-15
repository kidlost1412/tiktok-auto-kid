@extends('errors::layout')
@section('title', 'App đang bảo trì')
@section('code', '503')
@section('heading', 'App đang tạm dừng')
@section('message', 'App đang cập nhật hoặc khởi động lại, thường chỉ mất vài phút. Anh đợi một lát rồi tải lại nhé.')
@section('extra')
    <a class="btn" href="javascript:location.reload()">Tải lại</a>
@endsection
