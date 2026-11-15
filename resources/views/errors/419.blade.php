@extends('errors::layout')
@section('title', 'Phiên đã hết hạn')
@section('code', '419')
@section('heading', 'Phiên làm việc đã hết hạn')
@section('message', 'Trang đã mở quá lâu nên phiên bị hết hạn. Anh tải lại trang rồi thử làm lại thao tác vừa rồi.')
@section('extra')
    <a class="btn" href="javascript:location.reload()">Tải lại</a>
@endsection
