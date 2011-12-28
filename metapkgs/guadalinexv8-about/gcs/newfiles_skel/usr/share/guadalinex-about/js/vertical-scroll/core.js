$(document).ready(function() {

	$.localScroll();

	$("div.hoverBox a").fancybox({ 'hideOnContentClick': true }); 

	jQuery.easing.def = 'easeOutExpo';
	
	// FORM VALDATION //
	$("#basicForm").validate();

});	