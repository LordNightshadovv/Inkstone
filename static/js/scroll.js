document.addEventListener('DOMContentLoaded', function() {
    const scrollWrapper = document.querySelector('.horizontal-scroll-wrapper');

    if (scrollWrapper) {
        scrollWrapper.addEventListener('wheel', function(e) {
            e.preventDefault();
            scrollWrapper.scrollLeft += e.deltaY;
        });
    }
});