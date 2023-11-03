// Hi
var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

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

function newDetElement(det) {
    var cardDivElement = document.createElement('div');
    var classes = ['col-6', 'col-xs-6', 'col-sm-4', 'col-md-4', 'col-lg-3'];
    classes.forEach(det => cardDivElement.classList.add(det))
    // important for later stuff
    cardDivElement.id = `card-${det.id}`;
    cardDivElement.innerHTML = `
            <div class="card text-bg-dark border-light border-opacity-50">
                <a href="/inspect/${det.id}">
                    <img src="/upload/${det.filepath}" class="card-img-top">
                </a>
                <div class="card-body text-start">
                    <h6 class="card-title">
                        ${det.name}
                    </h5>
                    <p class="card-text">
                        <small class="text-muted">
                            ${det.timestamp}
                        </small>
                    </p>
                </div>
            </div>
        `;
    return cardDivElement;
}

function initial() {
    // test this
    fetch('/api/latest_data')
        .then(response => response.json())
        .then(data => {
            if (data.length < 1) {
                alertDiv.classList.remove("d-none");
                return;
            }
            data.forEach(det => {
                var cardElement = newDetElement(det);
                container.append(cardElement);
            });
        })
        .catch(error => console.error('Error:', error));
}

addEventListener("DOMContentLoaded", (event) => {
    let loadingDiv = document.getElementById("loading");

    console.log("We are currently at " + location.pathname);

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

    if (location.pathname == "/") {

    }

    if (location.pathname == "/live") {
        var video = document.getElementById("video");
        var img = document.getElementById("img");

        console.log("Live");

        socket.emit("start_stream");

        socket.on('recv_live_stream', function (data) {
            console.log(data)

            //const blob = new Blob([data.frame], { type: 'image/jpeg' });
            //const url = URL.createObjectURL(blob);

            img.src = data.frame;
        });
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
        var context = canvas.getContext('2d');

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

        socket.on('transformed_image', function (data) {
            img.src = data.transformed_image;
        });

        // video starts, we create our loop
        video.addEventListener('play', function () {
            setInterval(function () {
                if (!video.paused && !video.ended) {
                    // draw video frame to our hidden canvas
                    context.drawImage(video, 0, 0, canvas.width, canvas.height);
                    const imageData = canvas.toDataURL('image/jpeg');

                    // Send the image data to the server
                    socket.emit('video_data', { image_data: imageData });
                }
            }, 200);
        });

        video.addEventListener('loadedmetadata', function () {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            img.classList.remove("d-none");
            takePicBtn.parentElement.classList.remove("d-none");
        });

        starCamBtn.addEventListener('click', function () {
            let divElem = this.parentElement;
            // ugly
            loadingDiv.classList.remove("d-none");
            divElem.classList.add("d-none");
            // request access to the users camera
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(function (stream) {
                    // video.classList.remove("d-none");
                    video.srcObject = stream;
                    video.play();
                    loadingDiv.classList.add("d-none");
                })
                .catch(function (error) {
                    loadingDiv.classList.add("d-none");
                    divElem.classList.remove("d-none");
                    console.error('Error accessing the camera:', error);
                });
        });

        takePicBtn.addEventListener('click', function () {
            video.classList.add("d-none");
            video.srcObject.getVideoTracks()[0].stop();

            loadingDiv.classList.remove("d-none");

            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            // we have to draw the frame onto a canvas to get the image data
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

            loadingDiv.classList.add("d-none");

            // Stop the stream
            // make buttons appear and disappear
            takePicBtn.parentElement.classList.add("d-none");
            starCamBtn.parentElement.classList.remove("d-none");
        });
    }

})
