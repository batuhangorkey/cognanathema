// Hi

function refreshPage() {
    if (location.pathname == "/") {
        setTimeout(function () {
            location.reload();
        }, 1000 * 60 * 3);
    }
}

function isValidEmail(email) {
    var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function setGenderPreference(gender) {
    sessionStorage.setItem('view', gender);
}

function getGenderPreference() {
    return sessionStorage.getItem('view');
}

function isStrongPassword(password) {
    // Regular expressions for password strength
    // Minimum 8 and maximum 20 characters
    var lengthRegex = /^.{8,20}$/;
    // At least one uppercase letter
    var uppercaseRegex = /[A-Z]/;
    // At least one lowercase letter
    var lowercaseRegex = /[a-z]/;
    // At least one digit
    var digitRegex = /\d/;
    // At least one special character
    var specialCharRegex = /[!@#$%^&*(),.?":{}|<>_-]/;

    return (
        lengthRegex.test(password) &&
        uppercaseRegex.test(password) &&
        lowercaseRegex.test(password) &&
        digitRegex.test(password) &&
        specialCharRegex.test(password)
    );
}

function setLoading_(val) {
    let loadingElem = document.getElementById("loading");
    if (val) {
        console.log("Loading")
        loadingElem.classList.remove("d-none");
        console.log(loadingElem);
    }
    else {
        console.log("Loading off")
        loadingElem.classList.add("d-none");
        console.log(loadingElem);
    }
}

addEventListener("DOMContentLoaded", (event) => {
    console.log(location.pathname);
    let loadingElem = document.getElementById("loading");

    links = document.querySelectorAll("#collapsibleNavId > ul > li > .nav-link");

    links.forEach(element => {
        console.log(element.pathname);
        if (element.pathname == location.pathname) {
            element.classList.add("active");
        }
    });

    function checkPassword(passwordInput) {
        if (isStrongPassword(passwordInput.value)) {
            passwordInput.classList.remove('is-invalid');
            passwordInput.classList.add('is-valid');
            return true;
        }
        else {
            passwordInput.classList.add('is-invalid');
            passwordInput.classList.remove('is-valid');
            return false;
        }
    }

    if (location.pathname == "/profile" || location.pathname == "/signup") {
        password = document.getElementById('signupPassword');

        password.addEventListener('change', function (e) {
            checkPassword(password);
        });

        submitBtn = document.getElementById('submitBtn');
        console.log(submitBtn);

        submitBtn.addEventListener('click', function (e) {
            if (!checkPassword(password)) {
                e.preventDefault();
            }
        })
    }

    if (location.pathname == "/profile") {
        var canvas = document.createElement('canvas');

        let form = document.querySelector("form");
        var video = document.querySelector("video");
        let img = document.getElementById("img");

        let takePicBtn = document.getElementById('takePicBtn');
        let starCamBtn = document.getElementById('startCamBtn')
        let usePicBtn = document.getElementById("usePicBtn");

        usePicBtn.addEventListener('click', function (event) {
            fetch('/api/register/face', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image: img.src
                }),
            })
                .then(response => {
                    if (!response.ok) {
                        usePicBtn.parentElement.classList.remove("d-none");
                        return response.json().then((error) => console.log(error));
                    }
                    response.json().then((data) => {
                        // server gave us pass, lez go
                        console.log('Response from server:', data);
                    });
                })
                .catch(error => {
                    console.error('Error sending POST request:', error);
                });
        });

        starCamBtn.addEventListener('click', function () {
            let divElem = this.parentElement;
            // ugly
            loadingElem.classList.remove("d-none");
            divElem.classList.add("d-none");
            // request access to the users camera
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(function (stream) {
                    video.classList.remove("d-none");
                    video.srcObject = stream;
                    video.play();
                    loadingElem.classList.add("d-none");

                    video.addEventListener('loadedmetadata', function () {
                        takePicBtn.parentElement.classList.remove("d-none");
                    });
                })
                .catch(function (error) {
                    loadingElem.classList.add("d-none");
                    divElem.classList.remove("d-none");
                    console.error('Error accessing the camera:', error);
                });
        });

        takePicBtn.addEventListener('click', function () {
            video.classList.add("d-none");
            video.srcObject.getVideoTracks()[0].stop();

            loadingElem.classList.remove("d-none");

            // we have to draw the frame onto a canvas to get the image data
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            var context = canvas.getContext('2d');
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            // stupid js does not know jpg and jpeg is the same thing
            // never use png, it use much larger space
            var dataURL = canvas.toDataURL('image/jpeg');

            fetch('/api/upload/picture', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image: dataURL
                }),
            })
                .then(response => {
                    if (!response.ok) {
                        usePicBtn.parentElement.classList.remove("d-none");

                        return response.json().then((error) => console.log(error));
                    }
                    response.json().then((data) => {
                        // server gave us pass, lez go
                        console.log('Response from server:', data);

                        img.src = data.face;
                        img.classList.remove("d-none");
                    });
                })
                .catch(error => {
                    console.error('Error sending POST request:', error);
                });

            loadingElem.classList.add("d-none");

            // Stop the stream
            // make buttons appear and disappear
            takePicBtn.parentElement.classList.add("d-none");
            starCamBtn.parentElement.classList.remove("d-none");
        });
    }

})
