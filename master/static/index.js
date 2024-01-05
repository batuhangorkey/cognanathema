// Hi
const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
console.log(socket);

socket.on("connect", () => {
    console.log("Connected with id: " + socket.id);

});

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
    var backgroundColorClass = det.fake === 'Fake' ? 'bg-danger' : '';
    var borderColorClass = det.fake === 'Fake' ? 'border-danger' : 'border-success';

    cardDivElement.innerHTML = `
            <div class="card text-bg-dark border-opacity-100 ${borderColorClass}">
                <a href="/inspect/${det.id}">
                    <img src="/upload/${det.filepath}" class="card-img-top">
                </a>
                <div class="card-body text-start">
                    <h6 class="card-title ${backgroundColorClass}">
                        ${det.name} - ${det.fake}
                    </h6>
                    <p class="card-text">
                        <small class="text-muted">
                            ${det.timestamp}
                        </small>
                    </p>
                    <button class="btn btn-danger" onclick="deleteCard('${det.id}')">
                    Delete
                    </button>
                    <button class="btn btn-danger" onclick="deleteCard('${det.id}')">
                    Delete
                    </button>
                </div>
            </div>
        `;
    cardDivElement.dataset.cardId = det.id;
    return cardDivElement;
}

function uploadPhoto() {
    const form = document.getElementById('uploadForm');
    const formData = new FormData(form);
    const alert = document.getElementById('alert');

    console.log(formData);


    fetch('/api/detect/face', {
        method: 'POST',
        body: formData,
    })
        .then(response => response.json())
        .then(data => {
            displayFaceResult(data.result);
        })
        .catch(error => {
            console.error('Error:', error);

            alert.classList.remove("d-none");
            alert.innerHTML = error;
        });
}

function displayFaceResult(result) {
    const imgTag = document.getElementById('img');
    const alert = document.getElementById('alert');

    imgTag.src = result.face;

    // alert.innerHTML = `<p>${result.face}</p>`;

}

function confirmFace() {
    const faceImage = document.getElementById('img');
    const alert = document.getElementById("alert");

    const data = {
        name: document.querySelector('input[name="name"]').value,
        image: faceImage.src,
    };

    fetch('/api/register/face', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
    })
        .then(response => response.json())
        .then(serverResponse => {
            console.log(serverResponse);

            alert.classList.remove("d-none");
            alert.innerHTML = serverResponse.result;

            window.location.reload();
        })
        .catch(error => {
            console.error('Error:', error);

            alert.classList.remove("d-none");
            alert.innerHTML = error;
        });
}

function initial() {
    // test this
    let alertDiv = document.getElementById("alert");
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
        const socketLive = io.connect(location.protocol
            + '//' + document.domain
            + ':' + location.port
            + "/live");

        var video = document.getElementById("video");
        var imgThermal = document.getElementById("imgThermal");
        var imgCam = document.getElementById("imgCam");
        var streamDiv = document.getElementById("streamDiv");

        var min = document.getElementById("minDeg");
        var max = document.getElementById("maxDeg");
        var mean = document.getElementById("meanDeg");

        var thermalTable = document.getElementById("thermalTable");

        var totalWatchers = 0;
        var viewerCount = document.getElementById("viewerCount");

        console.log("Live pager");

        loadingDiv.classList.remove("d-none");

        socketLive.on("connect", () => {
            console.log("Connected with id: " + socket.id);
            socketLive.emit("join_stream");
        });

        socketLive.on('message', function (data) {
            console.log(data);
            if (data == "Looking for streamer") {

            }

            if (data.viewer_count) {
                viewerCount.innerHTML = data.viewer_count;
            }

            if (data == "streaming") {
                loadingDiv.classList.add("d-none");
                thermalTable.classList.remove("d-none");
                streamDiv.classList.remove("d-none");
            }

            if (data == "joined_room") {
                totalWatchers += 1;
                viewerCount.innerHTML = totalWatchers;
            }

            if (data == "left_room") {
                totalWatchers -= 1;
                if (totalWatchers < 0) {
                    totalWatchers = 0;
                }

                viewerCount.innerHTML = totalWatchers;
            }
        });

        socketLive.on('receive_cam_frame', function (data) {
            console.log(data);

            // const blob = new Blob([data.frame], { type: 'image/jpeg' });
            // const url = URL.createObjectURL(blob);

            imgCam.src = data.frame;
        });

        socketLive.on('receive_thermal_frame', function (data) {
            console.log(data);

            //const blob = new Blob([data.frame], { type: 'image/jpeg' });
            //const url = URL.createObjectURL(blob);

            imgThermal.src = data.frame;

            min.innerHTML = data.min + "'C";
            max.innerHTML = data.max + "'C";
            mean.innerHTML = data.mean + "'C";
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
        var alert = document.getElementById("alert");


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
            alert.classList.add("d-none");

            // request access to the users camera
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(function (stream) {
                    video.classList.remove("d-none");
                    video.srcObject = stream;
                    video.play();
                    loadingDiv.classList.add("d-none");
                })
                .catch(function (error) {
                    loadingDiv.classList.add("d-none");
                    divElem.classList.remove("d-none");

                    alert.classList.remove("d-none");
                    alert.innerHTML = error;
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
                        return response.json().then(
                            error => {
                                alert.classList.remove("d-none");
                                alert.innerHTML = error;
                                console.log(error);
                            });
                    }
                    response.json().then((data) => {
                        // server gave us pass, lez go
                        console.log('Response from server:', data);

                        alert.classList.add("d-none");
                        usePicBtn.parentElement.classList.remove("d-none");

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
