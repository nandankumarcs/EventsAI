from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from apps.events.models import MovieEvent, SportEvent

IST = ZoneInfo("Asia/Kolkata")

MOVIE_VENUES = {
    "New Delhi": [
        {
            "venue_name": "PVR Directors Cut",
            "venue_area": "Vasant Kunj",
            "venue_address": "DLF Emporio, Nelson Mandela Marg, New Delhi",
            "state": "Delhi",
        },
        {
            "venue_name": "INOX Nehru Place",
            "venue_area": "Nehru Place",
            "venue_address": "Epicuria Mall, Nehru Place, New Delhi",
            "state": "Delhi",
        },
    ],
    "Gurugram": [
        {
            "venue_name": "PVR Ambience",
            "venue_area": "DLF Phase 3",
            "venue_address": "Ambience Mall, NH-8, Gurugram",
            "state": "Haryana",
        },
        {
            "venue_name": "INOX WorldMark",
            "venue_area": "Sector 65",
            "venue_address": "WorldMark Gurugram, Sector 65, Gurugram",
            "state": "Haryana",
        },
    ],
    "Mumbai": [
        {
            "venue_name": "Maison PVR",
            "venue_area": "Bandra Kurla Complex",
            "venue_address": "Jio World Drive, BKC, Mumbai",
            "state": "Maharashtra",
        },
        {
            "venue_name": "PVR Phoenix",
            "venue_area": "Lower Parel",
            "venue_address": "Phoenix Palladium, Lower Parel, Mumbai",
            "state": "Maharashtra",
        },
    ],
    "Bengaluru": [
        {
            "venue_name": "PVR Orion Mall",
            "venue_area": "Rajajinagar",
            "venue_address": "Orion Mall, Rajajinagar, Bengaluru",
            "state": "Karnataka",
        },
        {
            "venue_name": "INOX Mantri Square",
            "venue_area": "Malleshwaram",
            "venue_address": "Mantri Square Mall, Malleshwaram, Bengaluru",
            "state": "Karnataka",
        },
    ],
    "Hyderabad": [
        {
            "venue_name": "AMB Cinemas",
            "venue_area": "Gachibowli",
            "venue_address": "Sarath City Capital Mall, Gachibowli, Hyderabad",
            "state": "Telangana",
        },
        {
            "venue_name": "PVR Next Galleria",
            "venue_area": "Panjagutta",
            "venue_address": "Next Galleria Mall, Panjagutta, Hyderabad",
            "state": "Telangana",
        },
    ],
    "Chennai": [
        {
            "venue_name": "Palazzo Cinemas",
            "venue_area": "Vadapalani",
            "venue_address": "Nexus Vijaya Mall, Vadapalani, Chennai",
            "state": "Tamil Nadu",
        },
        {
            "venue_name": "Sathyam Cinemas",
            "venue_area": "Royapettah",
            "venue_address": "8, Thiru Vi Ka Road, Royapettah, Chennai",
            "state": "Tamil Nadu",
        },
    ],
    "Kolkata": [
        {
            "venue_name": "INOX Quest Mall",
            "venue_area": "Park Circus",
            "venue_address": "Quest Mall, Ballygunge, Kolkata",
            "state": "West Bengal",
        },
        {
            "venue_name": "PVR Diamond Plaza",
            "venue_area": "Jessore Road",
            "venue_address": "Diamond Plaza Mall, Dum Dum, Kolkata",
            "state": "West Bengal",
        },
    ],
    "Ahmedabad": [
        {
            "venue_name": "PVR Acropolis",
            "venue_area": "Thaltej",
            "venue_address": "Acropolis Mall, SG Highway, Ahmedabad",
            "state": "Gujarat",
        },
        {
            "venue_name": "Cinepolis Alpha One",
            "venue_area": "Vastrapur",
            "venue_address": "Alpha One Mall, Vastrapur, Ahmedabad",
            "state": "Gujarat",
        },
    ],
    "Pune": [
        {
            "venue_name": "PVR Phoenix Marketcity",
            "venue_area": "Viman Nagar",
            "venue_address": "Phoenix Marketcity, Viman Nagar, Pune",
            "state": "Maharashtra",
        },
        {
            "venue_name": "INOX Amanora",
            "venue_area": "Hadapsar",
            "venue_address": "Amanora Mall, Hadapsar, Pune",
            "state": "Maharashtra",
        },
    ],
}

SPORT_CITY_TO_VENUE = {
    "Ahmedabad": {
        "venue_name": "Narendra Modi Stadium",
        "venue_area": "Motera",
        "venue_address": "Motera, Ahmedabad",
        "state": "Gujarat",
    },
    "Bengaluru": {
        "venue_name": "M Chinnaswamy Stadium",
        "venue_area": "MG Road",
        "venue_address": "Cubbon Road, Bengaluru",
        "state": "Karnataka",
    },
    "Chennai": {
        "venue_name": "MA Chidambaram Stadium",
        "venue_area": "Chepauk",
        "venue_address": "Wallajah Road, Chennai",
        "state": "Tamil Nadu",
    },
    "Delhi": {
        "venue_name": "Arun Jaitley Stadium",
        "venue_area": "Bahadur Shah Zafar Marg",
        "venue_address": "New Delhi",
        "state": "Delhi",
    },
    "Dharamshala": {
        "venue_name": "HPCA Stadium",
        "venue_area": "Dharamshala",
        "venue_address": "Dharamshala, Himachal Pradesh",
        "state": "Himachal Pradesh",
    },
    "Guwahati": {
        "venue_name": "Barsapara Cricket Stadium",
        "venue_area": "Barsapara",
        "venue_address": "Barsapara, Guwahati",
        "state": "Assam",
    },
    "Hyderabad": {
        "venue_name": "Rajiv Gandhi International Stadium",
        "venue_area": "Uppal",
        "venue_address": "Uppal, Hyderabad",
        "state": "Telangana",
    },
    "Jaipur": {
        "venue_name": "Sawai Mansingh Stadium",
        "venue_area": "Jyoti Nagar",
        "venue_address": "Jaipur, Rajasthan",
        "state": "Rajasthan",
    },
    "Kolkata": {
        "venue_name": "Eden Gardens",
        "venue_area": "Maidan",
        "venue_address": "B B D Bagh, Kolkata",
        "state": "West Bengal",
    },
    "Lucknow": {
        "venue_name": "Ekana Cricket Stadium",
        "venue_area": "Gomti Nagar",
        "venue_address": "Gomti Nagar Extension, Lucknow",
        "state": "Uttar Pradesh",
    },
    "Mumbai": {
        "venue_name": "Wankhede Stadium",
        "venue_area": "Churchgate",
        "venue_address": "Churchgate, Mumbai",
        "state": "Maharashtra",
    },
    "New Chandigarh": {
        "venue_name": "Maharaja Yadavindra Singh Stadium",
        "venue_area": "Mullanpur",
        "venue_address": "New Chandigarh, Punjab",
        "state": "Punjab",
    },
    "Raipur": {
        "venue_name": "Shaheed Veer Narayan Singh Stadium",
        "venue_area": "Naya Raipur",
        "venue_address": "Atal Nagar, Raipur",
        "state": "Chhattisgarh",
    },
}

TEAM_TO_ATHLETES = {
    "Chennai Super Kings": ["Ruturaj Gaikwad", "Ravindra Jadeja", "Matheesha Pathirana"],
    "Delhi Capitals": ["Axar Patel", "Kuldeep Yadav", "KL Rahul"],
    "Gujarat Titans": ["Shubman Gill", "Rashid Khan", "Sai Sudharsan"],
    "Kolkata Knight Riders": ["Andre Russell", "Sunil Narine", "Rinku Singh"],
    "Lucknow Super Giants": ["Nicholas Pooran", "Ravi Bishnoi", "Ayush Badoni"],
    "Mumbai Indians": ["Hardik Pandya", "Jasprit Bumrah", "Suryakumar Yadav"],
    "Punjab Kings": ["Shreyas Iyer", "Arshdeep Singh", "Yuzvendra Chahal"],
    "Rajasthan Royals": ["Sanju Samson", "Yashasvi Jaiswal", "Dhruv Jurel"],
    "Royal Challengers Bengaluru": ["Virat Kohli", "Rajat Patidar", "Josh Hazlewood"],
    "Sunrisers Hyderabad": ["Pat Cummins", "Abhishek Sharma", "Heinrich Klaasen"],
    "Mohun Bagan SG": ["Dimitri Petratos", "Jason Cummings", "Subhasish Bose"],
    "East Bengal FC": ["Cleiton Silva", "Saul Crespo", "Naorem Mahesh Singh"],
    "Bengaluru FC": ["Sunil Chhetri", "Javi Hernandez", "Gurpreet Singh Sandhu"],
    "Mumbai City FC": ["Lallianzuala Chhangte", "Jorge Pereyra Diaz", "Akash Mishra"],
    "FC Goa": ["Brison Fernandes", "Carl McHugh", "Jay Gupta"],
    "Kerala Blasters FC": ["Adrian Luna", "Noah Sadaoui", "Sachin Suresh"],
    "Odisha FC": ["Diego Mauricio", "Ahmed Jahouh", "Amrinder Singh"],
    "Chennaiyin FC": ["Connor Shields", "Ninthoinganba Meetei", "Debjit Majumder"],
    "Patna Pirates": ["Sachin Tanwar", "Ankit Jaglan", "Neeraj Kumar"],
    "Puneri Paltan": ["Aslam Inamdar", "Mohit Goyat", "Sanket Sawant"],
    "Jaipur Pink Panthers": ["Arjun Deshwal", "Reza Mirbagheri", "Sunil Kumar"],
    "U Mumba": ["Guman Singh", "Rinku", "Surinder Singh"],
    "Bengaluru Bulls": ["Pardeep Narwal", "Bharat Hooda", "Saurabh Nandal"],
    "Haryana Steelers": ["Mohammadreza Shadloui", "Vinay", "Jaideep"],
    "Tamil Thalaivas": ["Nitesh Kumar", "Narender Kandola", "Sahil Gulia"],
    "Dabang Delhi KC": ["Naveen Kumar", "Ashu Malik", "Yogesh"],
    "UP Yoddhas": ["Pardeep Narwal", "Sumit", "Surender Gill"],
}

MOVIE_CATALOG = [
    {
        "title": "Alpha",
        "release_date": date(2026, 4, 17),
        "runtime_minutes": 148,
        "certification": "UA",
        "genres": ["Action", "Spy Thriller"],
        "cast": ["Alia Bhatt", "Sharvari Wagh", "Bobby Deol"],
        "directors": ["Shiv Rawail"],
        "languages": ["Hindi", "Telugu", "Tamil"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "YRF Spy Universe",
        "synopsis": "Two field operatives race across continents to shut down a covert weapons network.",
        "viewer_rating": Decimal("4.2"),
        "content_origin": "real",
    },
    {
        "title": "Bhooth Bangla",
        "release_date": date(2026, 4, 17),
        "runtime_minutes": 136,
        "certification": "UA",
        "genres": ["Comedy", "Horror"],
        "cast": ["Akshay Kumar", "Tabu", "Wamiqa Gabbi"],
        "directors": ["Priyadarshan"],
        "languages": ["Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A cursed estate turns into a comic haunted-house mystery for an unlikely group of heirs.",
        "viewer_rating": Decimal("3.9"),
        "content_origin": "real",
    },
    {
        "title": "Mohiniyattam",
        "release_date": date(2026, 4, 10),
        "runtime_minutes": 132,
        "certification": "U",
        "genres": ["Dark Comedy", "Drama"],
        "cast": ["Saiju Kurup", "Kalaranjini", "Suraj Venjaramoodu"],
        "directors": ["Krishnadas Murali"],
        "languages": ["Malayalam"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A family’s polite façade crumbles when a buried secret resurfaces during festival season.",
        "viewer_rating": Decimal("4.0"),
        "content_origin": "real",
    },
    {
        "title": "Avengers: Doomsday",
        "release_date": date(2026, 5, 1),
        "runtime_minutes": 164,
        "certification": "UA",
        "genres": ["Action", "Sci-Fi", "Adventure"],
        "cast": ["Robert Downey Jr.", "Pedro Pascal", "Vanessa Kirby"],
        "directors": ["Anthony Russo", "Joe Russo"],
        "languages": ["English", "Hindi", "Tamil", "Telugu"],
        "formats": ["2D", "IMAX 3D", "4DX 3D"],
        "franchise": "Marvel Cinematic Universe",
        "synopsis": "Earth’s mightiest heroes reunite to stop a multiversal tyrant from rewriting reality.",
        "viewer_rating": Decimal("4.5"),
        "content_origin": "real",
    },
    {
        "title": "Mission: Impossible - The Final Reckoning",
        "release_date": date(2025, 5, 23),
        "runtime_minutes": 169,
        "certification": "UA",
        "genres": ["Action", "Thriller"],
        "cast": ["Tom Cruise", "Hayley Atwell", "Simon Pegg"],
        "directors": ["Christopher McQuarrie"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "Mission: Impossible",
        "synopsis": "Ethan Hunt faces a final global mission against an intelligence weapon no one can control.",
        "viewer_rating": Decimal("4.3"),
        "content_origin": "real",
    },
    {
        "title": "The Odyssey",
        "release_date": date(2026, 7, 17),
        "runtime_minutes": 170,
        "certification": "UA",
        "genres": ["Epic", "Adventure", "Drama"],
        "cast": ["Matt Damon", "Tom Holland", "Anne Hathaway"],
        "directors": ["Christopher Nolan"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "IMAX 70mm"],
        "franchise": "",
        "synopsis": "Odysseus fights the sea, myth, and memory on a long road home after war.",
        "viewer_rating": Decimal("4.6"),
        "content_origin": "real",
    },
    {
        "title": "Spider-Man: Brand New Day",
        "release_date": date(2026, 7, 31),
        "runtime_minutes": 142,
        "certification": "UA",
        "genres": ["Superhero", "Adventure"],
        "cast": ["Tom Holland", "Zendaya", "Jacob Batalon"],
        "directors": ["Destin Daniel Cretton"],
        "languages": ["English", "Hindi", "Tamil", "Telugu"],
        "formats": ["2D", "IMAX 3D"],
        "franchise": "Spider-Man",
        "synopsis": "Peter Parker rebuilds his life while a new threat hunts every trace of his secret past.",
        "viewer_rating": Decimal("4.4"),
        "content_origin": "real",
    },
    {
        "title": "Toy Story 5",
        "release_date": date(2026, 6, 19),
        "runtime_minutes": 108,
        "certification": "U",
        "genres": ["Animation", "Family", "Comedy"],
        "cast": ["Tom Hanks", "Tim Allen", "Joan Cusack"],
        "directors": ["Andrew Stanton"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "3D"],
        "franchise": "Toy Story",
        "synopsis": "Woody and Buzz navigate a new generation of play in a world full of smart devices.",
        "viewer_rating": Decimal("4.1"),
        "content_origin": "real",
    },
    {
        "title": "Shrek 5",
        "release_date": date(2026, 12, 23),
        "runtime_minutes": 112,
        "certification": "U",
        "genres": ["Animation", "Comedy", "Family"],
        "cast": ["Mike Myers", "Eddie Murphy", "Cameron Diaz"],
        "directors": ["Walt Dohrn"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "3D"],
        "franchise": "Shrek",
        "synopsis": "Far Far Away gets a fresh fairy-tale mess when Shrek is pulled back into royal chaos.",
        "viewer_rating": Decimal("4.0"),
        "content_origin": "real",
    },
    {
        "title": "The Super Mario Bros. Movie 2",
        "release_date": date(2026, 4, 3),
        "runtime_minutes": 104,
        "certification": "U",
        "genres": ["Animation", "Adventure"],
        "cast": ["Chris Pratt", "Anya Taylor-Joy", "Charlie Day"],
        "directors": ["Aaron Horvath", "Michael Jelenic"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "3D"],
        "franchise": "Super Mario Bros.",
        "synopsis": "Mario and Luigi face a new kingdom-wide threat that sends them far beyond the Mushroom Kingdom.",
        "viewer_rating": Decimal("3.8"),
        "content_origin": "real",
    },
    {
        "title": "Love and War",
        "release_date": date(2026, 3, 20),
        "runtime_minutes": 158,
        "certification": "UA",
        "genres": ["Romance", "Drama", "Period"],
        "cast": ["Ranbir Kapoor", "Alia Bhatt", "Vicky Kaushal"],
        "directors": ["Sanjay Leela Bhansali"],
        "languages": ["Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A wartime love triangle tests loyalty, sacrifice, and impossible choices.",
        "viewer_rating": Decimal("4.1"),
        "content_origin": "real",
    },
    {
        "title": "Naagzilla",
        "release_date": date(2026, 8, 14),
        "runtime_minutes": 130,
        "certification": "UA",
        "genres": ["Fantasy", "Comedy"],
        "cast": ["Kartik Aaryan", "Triptii Dimri", "Paresh Rawal"],
        "directors": ["Mrighdeep Singh Lamba"],
        "languages": ["Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A reluctant hero discovers that his family curse is also his weirdest superpower.",
        "viewer_rating": Decimal("3.7"),
        "content_origin": "real",
    },
    {
        "title": "Chhaava",
        "release_date": date(2025, 2, 14),
        "runtime_minutes": 161,
        "certification": "UA",
        "genres": ["Historical", "Action", "Drama"],
        "cast": ["Vicky Kaushal", "Rashmika Mandanna", "Akshaye Khanna"],
        "directors": ["Laxman Utekar"],
        "languages": ["Hindi"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "",
        "synopsis": "A warrior king rises to protect legacy, land, and a fragile empire.",
        "viewer_rating": Decimal("4.4"),
        "content_origin": "real",
    },
    {
        "title": "Stree 2",
        "release_date": date(2024, 8, 15),
        "runtime_minutes": 147,
        "certification": "UA",
        "genres": ["Horror", "Comedy"],
        "cast": ["Rajkummar Rao", "Shraddha Kapoor", "Pankaj Tripathi"],
        "directors": ["Amar Kaushik"],
        "languages": ["Hindi"],
        "formats": ["2D"],
        "franchise": "Maddock Horror Comedy Universe",
        "synopsis": "Chanderi’s favorite nightmare returns with a bigger supernatural problem.",
        "viewer_rating": Decimal("4.3"),
        "content_origin": "real",
    },
    {
        "title": "Kalki 2898 AD",
        "release_date": date(2024, 6, 27),
        "runtime_minutes": 176,
        "certification": "UA",
        "genres": ["Sci-Fi", "Action", "Mythology"],
        "cast": ["Prabhas", "Deepika Padukone", "Amitabh Bachchan"],
        "directors": ["Nag Ashwin"],
        "languages": ["Telugu", "Hindi", "Tamil"],
        "formats": ["2D", "IMAX 2D", "4DX"],
        "franchise": "",
        "synopsis": "A bounty hunter is pulled into an ancient prophecy at the end of a broken world.",
        "viewer_rating": Decimal("4.2"),
        "content_origin": "real",
    },
    {
        "title": "Pushpa 2: The Rule",
        "release_date": date(2024, 12, 5),
        "runtime_minutes": 182,
        "certification": "A",
        "genres": ["Action", "Drama"],
        "cast": ["Allu Arjun", "Rashmika Mandanna", "Fahadh Faasil"],
        "directors": ["Sukumar"],
        "languages": ["Telugu", "Hindi", "Tamil"],
        "formats": ["2D"],
        "franchise": "Pushpa",
        "synopsis": "Pushpa’s empire grows, but every victory brings a more dangerous rival to the table.",
        "viewer_rating": Decimal("4.0"),
        "content_origin": "real",
    },
    {
        "title": "Coolie",
        "release_date": date(2025, 8, 14),
        "runtime_minutes": 156,
        "certification": "UA",
        "genres": ["Action", "Thriller"],
        "cast": ["Rajinikanth", "Nagarjuna", "Upendra"],
        "directors": ["Lokesh Kanagaraj"],
        "languages": ["Tamil", "Hindi", "Telugu"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "",
        "synopsis": "An aging enforcer is dragged back into the world that made him legendary.",
        "viewer_rating": Decimal("4.3"),
        "content_origin": "real",
    },
    {
        "title": "War 2",
        "release_date": date(2025, 8, 14),
        "runtime_minutes": 151,
        "certification": "UA",
        "genres": ["Action", "Spy Thriller"],
        "cast": ["Hrithik Roshan", "NTR Jr.", "Kiara Advani"],
        "directors": ["Ayan Mukerji"],
        "languages": ["Hindi", "Tamil", "Telugu"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "YRF Spy Universe",
        "synopsis": "Kabir’s next mission pits him against an enemy who never attacks the same way twice.",
        "viewer_rating": Decimal("4.2"),
        "content_origin": "real",
    },
    {
        "title": "L2: Empuraan",
        "release_date": date(2025, 3, 27),
        "runtime_minutes": 179,
        "certification": "UA",
        "genres": ["Action", "Political Thriller"],
        "cast": ["Mohanlal", "Prithviraj Sukumaran", "Manju Warrier"],
        "directors": ["Prithviraj Sukumaran"],
        "languages": ["Malayalam", "Hindi", "Tamil"],
        "formats": ["2D"],
        "franchise": "Lucifer",
        "synopsis": "A shadow network wakes up when Khureshi-Ab’raam returns to settle unfinished business.",
        "viewer_rating": Decimal("4.1"),
        "content_origin": "real",
    },
    {
        "title": "Kuberaa",
        "release_date": date(2025, 6, 20),
        "runtime_minutes": 153,
        "certification": "UA",
        "genres": ["Crime", "Drama"],
        "cast": ["Dhanush", "Nagarjuna", "Rashmika Mandanna"],
        "directors": ["Sekhar Kammula"],
        "languages": ["Telugu", "Tamil", "Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A penniless drifter and a power broker collide in a story about wealth and survival.",
        "viewer_rating": Decimal("4.0"),
        "content_origin": "real",
    },
    {
        "title": "The Raja Saab",
        "release_date": date(2025, 12, 5),
        "runtime_minutes": 149,
        "certification": "UA",
        "genres": ["Horror", "Comedy", "Romance"],
        "cast": ["Prabhas", "Malavika Mohanan", "Nidhhi Agerwal"],
        "directors": ["Maruthi"],
        "languages": ["Telugu", "Hindi", "Tamil"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A charming prince with terrible luck steps into a mansion where nothing stays dead.",
        "viewer_rating": Decimal("3.8"),
        "content_origin": "real",
    },
    {
        "title": "Maharaja",
        "release_date": date(2024, 6, 14),
        "runtime_minutes": 141,
        "certification": "UA",
        "genres": ["Thriller", "Drama"],
        "cast": ["Vijay Sethupathi", "Anurag Kashyap", "Mamta Mohandas"],
        "directors": ["Nithilan Saminathan"],
        "languages": ["Tamil", "Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A quiet barber’s missing household object unravels into a haunting revenge mystery.",
        "viewer_rating": Decimal("4.4"),
        "content_origin": "real",
    },
    {
        "title": "Sitaare Zameen Par",
        "release_date": date(2025, 6, 20),
        "runtime_minutes": 144,
        "certification": "U",
        "genres": ["Comedy", "Drama", "Family"],
        "cast": ["Aamir Khan", "Genelia D'Souza", "Darsheel Safary"],
        "directors": ["R. S. Prasanna"],
        "languages": ["Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A coach and a spirited team discover purpose through competition and compassion.",
        "viewer_rating": Decimal("4.1"),
        "content_origin": "real",
    },
    {
        "title": "Sinners",
        "release_date": date(2025, 4, 18),
        "runtime_minutes": 137,
        "certification": "A",
        "genres": ["Horror", "Thriller"],
        "cast": ["Michael B. Jordan", "Hailee Steinfeld", "Jack O'Connell"],
        "directors": ["Ryan Coogler"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "",
        "synopsis": "A Southern town with a violent past turns on the people trying to redeem it.",
        "viewer_rating": Decimal("4.0"),
        "content_origin": "real",
    },
    {
        "title": "Mickey 17",
        "release_date": date(2025, 3, 7),
        "runtime_minutes": 139,
        "certification": "UA",
        "genres": ["Sci-Fi", "Dark Comedy"],
        "cast": ["Robert Pattinson", "Naomi Ackie", "Steven Yeun"],
        "directors": ["Bong Joon Ho"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "",
        "synopsis": "A disposable worker on an ice colony keeps getting replaced, but one copy refuses to disappear.",
        "viewer_rating": Decimal("4.1"),
        "content_origin": "real",
    },
    {
        "title": "F1",
        "release_date": date(2025, 6, 27),
        "runtime_minutes": 150,
        "certification": "UA",
        "genres": ["Sports", "Drama"],
        "cast": ["Brad Pitt", "Damson Idris", "Kerry Condon"],
        "directors": ["Joseph Kosinski"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "",
        "synopsis": "A veteran driver returns to the paddock to mentor a prodigy and save a struggling team.",
        "viewer_rating": Decimal("4.0"),
        "content_origin": "real",
    },
    {
        "title": "Wicked: For Good",
        "release_date": date(2025, 11, 21),
        "runtime_minutes": 152,
        "certification": "U",
        "genres": ["Musical", "Fantasy"],
        "cast": ["Cynthia Erivo", "Ariana Grande", "Jonathan Bailey"],
        "directors": ["Jon M. Chu"],
        "languages": ["English", "Hindi"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "Wicked",
        "synopsis": "Elphaba and Glinda’s choices change Oz forever as friendship and power pull them apart.",
        "viewer_rating": Decimal("4.2"),
        "content_origin": "real",
    },
    {
        "title": "28 Years Later",
        "release_date": date(2025, 6, 20),
        "runtime_minutes": 126,
        "certification": "A",
        "genres": ["Horror", "Thriller"],
        "cast": ["Jodie Comer", "Aaron Taylor-Johnson", "Ralph Fiennes"],
        "directors": ["Danny Boyle"],
        "languages": ["English", "Hindi"],
        "formats": ["2D"],
        "franchise": "28 Days Later",
        "synopsis": "Humanity survives in fragments while a new strain spreads beyond every wall built to stop it.",
        "viewer_rating": Decimal("4.0"),
        "content_origin": "real",
    },
    {
        "title": "Project Astra",
        "release_date": date(2026, 9, 11),
        "runtime_minutes": 138,
        "certification": "UA",
        "genres": ["Sci-Fi", "Thriller"],
        "cast": ["Radhika Apte", "Ishaan Khatter", "Rahul Bose"],
        "directors": ["Anvita Dutt"],
        "languages": ["Hindi", "English"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "",
        "synopsis": "A lunar telescope mission uncovers a pattern in the sky that no government wants discussed.",
        "viewer_rating": Decimal("3.9"),
        "content_origin": "synthetic",
    },
    {
        "title": "Delhi Dreams",
        "release_date": date(2026, 6, 5),
        "runtime_minutes": 124,
        "certification": "U",
        "genres": ["Drama", "Romance"],
        "cast": ["Triptii Dimri", "Vikrant Massey", "Tillotama Shome"],
        "directors": ["Akarsh Khurana"],
        "languages": ["Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "Three strangers in the capital discover how ambition reshapes friendship and love.",
        "viewer_rating": Decimal("3.8"),
        "content_origin": "synthetic",
    },
    {
        "title": "Marina Protocol",
        "release_date": date(2026, 10, 2),
        "runtime_minutes": 146,
        "certification": "UA",
        "genres": ["Action", "Thriller"],
        "cast": ["Aditi Rao Hydari", "Atharvaa", "Prakash Raj"],
        "directors": ["Sudha Kongara"],
        "languages": ["Tamil", "Hindi", "Telugu"],
        "formats": ["2D", "IMAX 2D"],
        "franchise": "",
        "synopsis": "A naval code breach in Chennai exposes a conspiracy that stretches from the docks to Delhi.",
        "viewer_rating": Decimal("4.0"),
        "content_origin": "synthetic",
    },
    {
        "title": "Midnight Monsoon",
        "release_date": date(2026, 7, 24),
        "runtime_minutes": 118,
        "certification": "UA",
        "genres": ["Mystery", "Thriller"],
        "cast": ["Sai Pallavi", "Roshan Mathew", "Vijay Varma"],
        "directors": ["Jeo Baby"],
        "languages": ["Malayalam", "Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A storm-soaked train journey strands five passengers with secrets that refuse to stay buried.",
        "viewer_rating": Decimal("4.1"),
        "content_origin": "synthetic",
    },
    {
        "title": "Monsoon Heist",
        "release_date": date(2026, 8, 28),
        "runtime_minutes": 133,
        "certification": "UA",
        "genres": ["Crime", "Comedy"],
        "cast": ["Rajkummar Rao", "Sobhita Dhulipala", "Gulshan Devaiah"],
        "directors": ["Raj & DK"],
        "languages": ["Hindi"],
        "formats": ["2D"],
        "franchise": "",
        "synopsis": "A washed-up fixer assembles the worst possible team for a robbery during Mumbai’s rainiest week.",
        "viewer_rating": Decimal("3.9"),
        "content_origin": "synthetic",
    },
]

IPL_2026_MATCHES = [
    (1, "28-MAR-26", "Sat", "7:30 PM", "Sunrisers Hyderabad", "Royal Challengers Bengaluru", "Bengaluru"),
    (2, "29-MAR-26", "Sun", "7:30 PM", "Kolkata Knight Riders", "Mumbai Indians", "Mumbai"),
    (3, "30-MAR-26", "Mon", "7:30 PM", "Chennai Super Kings", "Rajasthan Royals", "Guwahati"),
    (4, "31-MAR-26", "Tue", "7:30 PM", "Gujarat Titans", "Punjab Kings", "New Chandigarh"),
    (5, "01-APR-26", "Wed", "7:30 PM", "Delhi Capitals", "Lucknow Super Giants", "Lucknow"),
    (6, "02-APR-26", "Thu", "7:30 PM", "Sunrisers Hyderabad", "Kolkata Knight Riders", "Kolkata"),
    (7, "03-APR-26", "Fri", "7:30 PM", "Punjab Kings", "Chennai Super Kings", "Chennai"),
    (8, "04-APR-26", "Sat", "3:30 PM", "Mumbai Indians", "Delhi Capitals", "Delhi"),
    (9, "04-APR-26", "Sat", "7:30 PM", "Rajasthan Royals", "Gujarat Titans", "Ahmedabad"),
    (10, "05-APR-26", "Sun", "3:30 PM", "Lucknow Super Giants", "Sunrisers Hyderabad", "Hyderabad"),
    (11, "05-APR-26", "Sun", "7:30 PM", "Chennai Super Kings", "Royal Challengers Bengaluru", "Bengaluru"),
    (12, "06-APR-26", "Mon", "7:30 PM", "Punjab Kings", "Kolkata Knight Riders", "Kolkata"),
    (13, "07-APR-26", "Tue", "7:30 PM", "Mumbai Indians", "Rajasthan Royals", "Guwahati"),
    (14, "08-APR-26", "Wed", "7:30 PM", "Gujarat Titans", "Delhi Capitals", "Delhi"),
    (15, "09-APR-26", "Thu", "7:30 PM", "Lucknow Super Giants", "Kolkata Knight Riders", "Kolkata"),
    (16, "10-APR-26", "Fri", "7:30 PM", "Royal Challengers Bengaluru", "Rajasthan Royals", "Guwahati"),
    (17, "11-APR-26", "Sat", "3:30 PM", "Sunrisers Hyderabad", "Punjab Kings", "New Chandigarh"),
    (18, "11-APR-26", "Sat", "7:30 PM", "Delhi Capitals", "Chennai Super Kings", "Chennai"),
    (19, "12-APR-26", "Sun", "3:30 PM", "Gujarat Titans", "Lucknow Super Giants", "Lucknow"),
    (20, "12-APR-26", "Sun", "7:30 PM", "Royal Challengers Bengaluru", "Mumbai Indians", "Mumbai"),
    (21, "13-APR-26", "Mon", "7:30 PM", "Rajasthan Royals", "Sunrisers Hyderabad", "Hyderabad"),
    (22, "14-APR-26", "Tue", "7:30 PM", "Kolkata Knight Riders", "Chennai Super Kings", "Chennai"),
    (23, "15-APR-26", "Wed", "7:30 PM", "Lucknow Super Giants", "Royal Challengers Bengaluru", "Bengaluru"),
    (24, "16-APR-26", "Thu", "7:30 PM", "Punjab Kings", "Mumbai Indians", "Mumbai"),
    (25, "17-APR-26", "Fri", "7:30 PM", "Kolkata Knight Riders", "Gujarat Titans", "Ahmedabad"),
    (26, "18-APR-26", "Sat", "3:30 PM", "Delhi Capitals", "Royal Challengers Bengaluru", "Bengaluru"),
    (27, "18-APR-26", "Sat", "7:30 PM", "Chennai Super Kings", "Sunrisers Hyderabad", "Hyderabad"),
    (28, "19-APR-26", "Sun", "3:30 PM", "Rajasthan Royals", "Kolkata Knight Riders", "Kolkata"),
    (29, "19-APR-26", "Sun", "7:30 PM", "Lucknow Super Giants", "Punjab Kings", "New Chandigarh"),
    (30, "20-APR-26", "Mon", "7:30 PM", "Mumbai Indians", "Gujarat Titans", "Ahmedabad"),
    (31, "21-APR-26", "Tue", "7:30 PM", "Delhi Capitals", "Sunrisers Hyderabad", "Hyderabad"),
    (32, "22-APR-26", "Wed", "7:30 PM", "Rajasthan Royals", "Lucknow Super Giants", "Lucknow"),
    (33, "23-APR-26", "Thu", "7:30 PM", "Chennai Super Kings", "Mumbai Indians", "Mumbai"),
    (34, "24-APR-26", "Fri", "7:30 PM", "Gujarat Titans", "Royal Challengers Bengaluru", "Bengaluru"),
    (35, "25-APR-26", "Sat", "3:30 PM", "Punjab Kings", "Delhi Capitals", "Delhi"),
    (36, "25-APR-26", "Sat", "7:30 PM", "Sunrisers Hyderabad", "Rajasthan Royals", "Jaipur"),
    (37, "26-APR-26", "Sun", "3:30 PM", "Chennai Super Kings", "Gujarat Titans", "Ahmedabad"),
    (38, "26-APR-26", "Sun", "7:30 PM", "Kolkata Knight Riders", "Lucknow Super Giants", "Lucknow"),
    (39, "27-APR-26", "Mon", "7:30 PM", "Royal Challengers Bengaluru", "Delhi Capitals", "Delhi"),
    (40, "28-APR-26", "Tue", "7:30 PM", "Rajasthan Royals", "Punjab Kings", "New Chandigarh"),
    (41, "29-APR-26", "Wed", "7:30 PM", "Sunrisers Hyderabad", "Mumbai Indians", "Mumbai"),
    (42, "30-APR-26", "Thu", "7:30 PM", "Royal Challengers Bengaluru", "Gujarat Titans", "Ahmedabad"),
    (43, "01-MAY-26", "Fri", "7:30 PM", "Delhi Capitals", "Rajasthan Royals", "Jaipur"),
    (44, "02-MAY-26", "Sat", "7:30 PM", "Mumbai Indians", "Chennai Super Kings", "Chennai"),
    (45, "03-MAY-26", "Sun", "3:30 PM", "Kolkata Knight Riders", "Sunrisers Hyderabad", "Hyderabad"),
    (46, "03-MAY-26", "Sun", "7:30 PM", "Punjab Kings", "Gujarat Titans", "Ahmedabad"),
    (47, "04-MAY-26", "Mon", "7:30 PM", "Lucknow Super Giants", "Mumbai Indians", "Mumbai"),
    (48, "05-MAY-26", "Tue", "7:30 PM", "Chennai Super Kings", "Delhi Capitals", "Delhi"),
    (49, "06-MAY-26", "Wed", "7:30 PM", "Punjab Kings", "Sunrisers Hyderabad", "Hyderabad"),
    (50, "07-MAY-26", "Thu", "7:30 PM", "Royal Challengers Bengaluru", "Lucknow Super Giants", "Lucknow"),
    (51, "08-MAY-26", "Fri", "7:30 PM", "Kolkata Knight Riders", "Delhi Capitals", "Delhi"),
    (52, "09-MAY-26", "Sat", "7:30 PM", "Gujarat Titans", "Rajasthan Royals", "Jaipur"),
    (53, "10-MAY-26", "Sun", "3:30 PM", "Lucknow Super Giants", "Chennai Super Kings", "Chennai"),
    (54, "10-MAY-26", "Sun", "7:30 PM", "Mumbai Indians", "Royal Challengers Bengaluru", "Raipur"),
    (55, "11-MAY-26", "Mon", "7:30 PM", "Delhi Capitals", "Punjab Kings", "Dharamshala"),
    (56, "12-MAY-26", "Tue", "7:30 PM", "Sunrisers Hyderabad", "Gujarat Titans", "Ahmedabad"),
    (57, "13-MAY-26", "Wed", "7:30 PM", "Kolkata Knight Riders", "Royal Challengers Bengaluru", "Raipur"),
    (58, "14-MAY-26", "Thu", "7:30 PM", "Mumbai Indians", "Punjab Kings", "Dharamshala"),
    (59, "15-MAY-26", "Fri", "7:30 PM", "Chennai Super Kings", "Lucknow Super Giants", "Lucknow"),
    (60, "16-MAY-26", "Sat", "7:30 PM", "Gujarat Titans", "Kolkata Knight Riders", "Kolkata"),
    (61, "17-MAY-26", "Sun", "3:30 PM", "Royal Challengers Bengaluru", "Punjab Kings", "Dharamshala"),
    (62, "17-MAY-26", "Sun", "7:30 PM", "Rajasthan Royals", "Delhi Capitals", "Delhi"),
    (63, "18-MAY-26", "Mon", "7:30 PM", "Sunrisers Hyderabad", "Chennai Super Kings", "Chennai"),
    (64, "19-MAY-26", "Tue", "7:30 PM", "Lucknow Super Giants", "Rajasthan Royals", "Jaipur"),
    (65, "20-MAY-26", "Wed", "7:30 PM", "Mumbai Indians", "Kolkata Knight Riders", "Kolkata"),
    (66, "21-MAY-26", "Thu", "7:30 PM", "Gujarat Titans", "Chennai Super Kings", "Chennai"),
    (67, "22-MAY-26", "Fri", "7:30 PM", "Royal Challengers Bengaluru", "Sunrisers Hyderabad", "Hyderabad"),
    (68, "23-MAY-26", "Sat", "7:30 PM", "Punjab Kings", "Lucknow Super Giants", "Lucknow"),
    (69, "24-MAY-26", "Sun", "3:30 PM", "Rajasthan Royals", "Mumbai Indians", "Mumbai"),
    (70, "24-MAY-26", "Sun", "7:30 PM", "Delhi Capitals", "Kolkata Knight Riders", "Kolkata"),
]

FOOTBALL_CLUBS = [
    "Mohun Bagan SG",
    "East Bengal FC",
    "Bengaluru FC",
    "Mumbai City FC",
    "FC Goa",
    "Kerala Blasters FC",
    "Odisha FC",
    "Chennaiyin FC",
]

FOOTBALL_VENUES = [
    {
        "city": "Kolkata",
        "state": "West Bengal",
        "venue_name": "Vivekananda Yuba Bharati Krirangan",
        "venue_area": "Salt Lake",
        "venue_address": "Salt Lake Stadium, Kolkata",
    },
    {
        "city": "Bengaluru",
        "state": "Karnataka",
        "venue_name": "Sree Kanteerava Stadium",
        "venue_area": "Ashok Nagar",
        "venue_address": "Sampangi Rama Nagar, Bengaluru",
    },
    {
        "city": "Mumbai",
        "state": "Maharashtra",
        "venue_name": "Mumbai Football Arena",
        "venue_area": "Andheri",
        "venue_address": "Andheri Sports Complex, Mumbai",
    },
    {
        "city": "Kochi",
        "state": "Kerala",
        "venue_name": "Jawaharlal Nehru Stadium",
        "venue_area": "Kaloor",
        "venue_address": "Kaloor, Kochi",
    },
    {
        "city": "Bhubaneswar",
        "state": "Odisha",
        "venue_name": "Kalinga Stadium",
        "venue_area": "Nayapalli",
        "venue_address": "Nayapalli, Bhubaneswar",
    },
    {
        "city": "Chennai",
        "state": "Tamil Nadu",
        "venue_name": "Jawaharlal Nehru Stadium",
        "venue_area": "Park Town",
        "venue_address": "Sydenhams Road, Chennai",
    },
]

KABADDI_TEAMS = [
    "Patna Pirates",
    "Puneri Paltan",
    "Jaipur Pink Panthers",
    "U Mumba",
    "Bengaluru Bulls",
    "Haryana Steelers",
    "Tamil Thalaivas",
    "Dabang Delhi KC",
    "UP Yoddhas",
]

KABADDI_VENUES = [
    {
        "city": "Noida",
        "state": "Uttar Pradesh",
        "venue_name": "Noida Indoor Stadium",
        "venue_area": "Sector 21A",
        "venue_address": "Noida Stadium Complex, Noida",
    },
    {
        "city": "Mumbai",
        "state": "Maharashtra",
        "venue_name": "NSCI Dome",
        "venue_area": "Worli",
        "venue_address": "NSCI Complex, Worli, Mumbai",
    },
    {
        "city": "Hyderabad",
        "state": "Telangana",
        "venue_name": "Gachibowli Indoor Stadium",
        "venue_area": "Gachibowli",
        "venue_address": "Gachibowli Sports Complex, Hyderabad",
    },
    {
        "city": "Jaipur",
        "state": "Rajasthan",
        "venue_name": "Sawai Mansingh Indoor Arena",
        "venue_area": "Lalkothi",
        "venue_address": "Lalkothi, Jaipur",
    },
    {
        "city": "Bengaluru",
        "state": "Karnataka",
        "venue_name": "Kanteerava Indoor Stadium",
        "venue_area": "Ashok Nagar",
        "venue_address": "Ashok Nagar, Bengaluru",
    },
    {
        "city": "Chennai",
        "state": "Tamil Nadu",
        "venue_name": "Nehru Indoor Stadium",
        "venue_area": "Park Town",
        "venue_address": "Park Town, Chennai",
    },
]

BADMINTON_MATCHUPS = [
    ("PV Sindhu", "Pusarla Gayatri"),
    ("Lakshya Sen", "Kidambi Srikanth"),
    ("H.S. Prannoy", "Priyanshu Rajawat"),
    ("Treesa Jolly / Gayatri Gopichand", "Tanisha Crasto / Ashwini Ponnappa"),
    ("Satwiksairaj Rankireddy / Chirag Shetty", "M.R. Arjun / Dhruv Kapila"),
    ("Aakarshi Kashyap", "Unnati Hooda"),
]

BADMINTON_VENUES = [
    {
        "city": "New Delhi",
        "state": "Delhi",
        "venue_name": "Indira Gandhi Indoor Stadium",
        "venue_area": "IP Estate",
        "venue_address": "Indraprastha Estate, New Delhi",
    },
    {
        "city": "Hyderabad",
        "state": "Telangana",
        "venue_name": "G. M. C. Balayogi Stadium",
        "venue_area": "Gachibowli",
        "venue_address": "Gachibowli, Hyderabad",
    },
    {
        "city": "Bengaluru",
        "state": "Karnataka",
        "venue_name": "Kanteerava Indoor Stadium",
        "venue_area": "Ashok Nagar",
        "venue_address": "Ashok Nagar, Bengaluru",
    },
]


def build_movie_events(reference_date: date) -> list[MovieEvent]:
    records: list[MovieEvent] = []
    cities = list(MOVIE_VENUES.keys())
    screening_times = [time(10, 15), time(13, 30), time(16, 45), time(19, 30), time(22, 15)]

    for movie_index, movie in enumerate(MOVIE_CATALOG):
        screenings_per_movie = 4 if movie["content_origin"] == "real" else 3

        for screening_index in range(screenings_per_movie):
            city = cities[(movie_index + screening_index) % len(cities)]
            venue = MOVIE_VENUES[city][screening_index % len(MOVIE_VENUES[city])]
            release_date = movie["release_date"]
            base_date = max(reference_date + timedelta(days=1 + screening_index), release_date)
            event_date = base_date + timedelta(days=(movie_index % 4) * 2 + screening_index * 3)
            start_time = screening_times[(movie_index + screening_index) % len(screening_times)]
            start_at = datetime.combine(event_date, start_time, tzinfo=IST)
            end_at = start_at + timedelta(minutes=movie["runtime_minutes"])
            format_label = movie["formats"][screening_index % len(movie["formats"])]
            city_price_offset = 80 if city in {"Mumbai", "Bengaluru", "Gurugram"} else 40
            format_price_offset = 140 if "IMAX" in format_label or "4DX" in format_label else 60
            min_price = 220 + city_price_offset + screening_index * 15
            max_price = min_price + format_price_offset
            listing_code = f"MOV-{movie_index + 1:03d}-{screening_index + 1:02d}"

            records.append(
                MovieEvent(
                    listing_code=listing_code,
                    title=movie["title"],
                    event_date=event_date,
                    start_at=start_at,
                    end_at=end_at,
                    city=city,
                    state=venue["state"],
                    venue_name=venue["venue_name"],
                    venue_area=venue["venue_area"],
                    venue_address=venue["venue_address"],
                    languages=movie["languages"],
                    min_price=min_price,
                    max_price=max_price,
                    tags=sorted(
                        {
                            *movie["genres"],
                            movie["content_origin"],
                            "premium" if max_price >= 450 else "accessible",
                            "weekend" if event_date.weekday() >= 5 else "weekday",
                        }
                    ),
                    metadata={
                        "seed_origin": movie["content_origin"],
                        "screening_number": screening_index + 1,
                    },
                    source_label=movie["content_origin"],
                    release_date=movie["release_date"],
                    runtime_minutes=movie["runtime_minutes"],
                    certification=movie["certification"],
                    genres=movie["genres"],
                    cast=movie["cast"],
                    directors=movie["directors"],
                    formats=[format_label],
                    franchise=movie["franchise"],
                    synopsis=movie["synopsis"],
                    viewer_rating=movie["viewer_rating"],
                    content_origin=movie["content_origin"],
                )
            )

    return records


def build_sport_events(reference_date: date) -> list[SportEvent]:
    records: list[SportEvent] = []
    records.extend(build_ipl_events(reference_date))
    records.extend(build_football_events(reference_date))
    records.extend(build_kabaddi_events(reference_date))
    records.extend(build_badminton_events(reference_date))
    return records


def build_ipl_events(reference_date: date) -> list[SportEvent]:
    records: list[SportEvent] = []

    for match_no, date_text, _day_name, time_text, home_team, away_team, venue_city in IPL_2026_MATCHES:
        event_date = datetime.strptime(date_text, "%d-%b-%y").date()
        if event_date <= reference_date:
            continue

        hour, minute = (15, 30) if time_text == "3:30 PM" else (19, 30)
        start_at = datetime.combine(event_date, time(hour, minute), tzinfo=IST)
        venue = SPORT_CITY_TO_VENUE[venue_city]
        featured_athletes = sorted(
            {
                *TEAM_TO_ATHLETES.get(home_team, []),
                *TEAM_TO_ATHLETES.get(away_team, []),
            }
        )

        records.append(
            SportEvent(
                listing_code=f"SPT-IPL-{match_no:03d}",
                title=f"{home_team} vs {away_team}",
                event_date=event_date,
                start_at=start_at,
                end_at=start_at + timedelta(hours=4),
                city="New Delhi" if venue_city == "Delhi" else venue_city,
                state=venue["state"],
                venue_name=venue["venue_name"],
                venue_area=venue["venue_area"],
                venue_address=venue["venue_address"],
                languages=["English", "Hindi"],
                min_price=750 if venue_city in {"Mumbai", "Bengaluru"} else 499,
                max_price=3200 if venue_city in {"Mumbai", "Bengaluru"} else 2400,
                tags=["cricket", "t20", "ipl", "league-match"],
                metadata={"seed_origin": "real", "schedule_source": "iplt20.com official PDF"},
                source_label="real",
                sport_type="Cricket",
                tournament_name="Indian Premier League 2026",
                season_label="IPL 2026",
                competition_stage="League",
                format_label="T20",
                home_team=home_team,
                away_team=away_team,
                participant_names=[home_team, away_team],
                featured_athletes=featured_athletes,
                organizer="BCCI",
                gate_open_at=start_at - timedelta(hours=2),
                match_number=match_no,
            )
        )

    return records


def build_football_events(reference_date: date) -> list[SportEvent]:
    records: list[SportEvent] = []
    base_date = max(reference_date + timedelta(days=35), date(2026, 7, 10))

    for index in range(24):
        home_team = FOOTBALL_CLUBS[index % len(FOOTBALL_CLUBS)]
        away_team = FOOTBALL_CLUBS[(index * 3 + 2) % len(FOOTBALL_CLUBS)]
        if home_team == away_team:
            away_team = FOOTBALL_CLUBS[(index + 1) % len(FOOTBALL_CLUBS)]

        venue = FOOTBALL_VENUES[index % len(FOOTBALL_VENUES)]
        event_date = base_date + timedelta(days=index * 2)
        start_at = datetime.combine(event_date, time(19, 30), tzinfo=IST)
        stage = "League" if index < 18 else ("Semi Final" if index < 22 else "Final")
        tournament = "Indian Super Cup 2026" if index < 12 else "Durand Cup 2026"

        records.append(
            SportEvent(
                listing_code=f"SPT-FBL-{index + 1:03d}",
                title=f"{home_team} vs {away_team}",
                event_date=event_date,
                start_at=start_at,
                end_at=start_at + timedelta(hours=2),
                city=venue["city"],
                state=venue["state"],
                venue_name=venue["venue_name"],
                venue_area=venue["venue_area"],
                venue_address=venue["venue_address"],
                languages=["English", "Hindi"],
                min_price=399,
                max_price=1899,
                tags=["football", "stadium", "club-football", "synthetic"],
                metadata={"seed_origin": "synthetic"},
                source_label="synthetic",
                sport_type="Football",
                tournament_name=tournament,
                season_label="2026",
                competition_stage=stage,
                format_label="90-minute match",
                home_team=home_team,
                away_team=away_team,
                participant_names=[home_team, away_team],
                featured_athletes=sorted(
                    {
                        *TEAM_TO_ATHLETES.get(home_team, []),
                        *TEAM_TO_ATHLETES.get(away_team, []),
                    }
                ),
                organizer="All India Football Federation",
                gate_open_at=start_at - timedelta(hours=1, minutes=30),
                match_number=index + 1,
            )
        )

    return records


def build_kabaddi_events(reference_date: date) -> list[SportEvent]:
    records: list[SportEvent] = []
    base_date = max(reference_date + timedelta(days=70), date(2026, 8, 20))

    for index in range(24):
        home_team = KABADDI_TEAMS[index % len(KABADDI_TEAMS)]
        away_team = KABADDI_TEAMS[(index * 2 + 3) % len(KABADDI_TEAMS)]
        if home_team == away_team:
            away_team = KABADDI_TEAMS[(index + 2) % len(KABADDI_TEAMS)]

        venue = KABADDI_VENUES[index % len(KABADDI_VENUES)]
        event_date = base_date + timedelta(days=index)
        start_at = datetime.combine(event_date, time(20, 0), tzinfo=IST)
        stage = "League" if index < 18 else ("Eliminator" if index < 22 else "Final")

        records.append(
            SportEvent(
                listing_code=f"SPT-KBD-{index + 1:03d}",
                title=f"{home_team} vs {away_team}",
                event_date=event_date,
                start_at=start_at,
                end_at=start_at + timedelta(hours=2),
                city=venue["city"],
                state=venue["state"],
                venue_name=venue["venue_name"],
                venue_area=venue["venue_area"],
                venue_address=venue["venue_address"],
                languages=["Hindi", "English"],
                min_price=299,
                max_price=1499,
                tags=["kabaddi", "indoor", "pro-kabaddi", "synthetic"],
                metadata={"seed_origin": "synthetic"},
                source_label="synthetic",
                sport_type="Kabaddi",
                tournament_name="Pro Kabaddi League 2026 Showcase",
                season_label="PKL 2026",
                competition_stage=stage,
                format_label="40-minute match",
                home_team=home_team,
                away_team=away_team,
                participant_names=[home_team, away_team],
                featured_athletes=sorted(
                    {
                        *TEAM_TO_ATHLETES.get(home_team, []),
                        *TEAM_TO_ATHLETES.get(away_team, []),
                    }
                ),
                organizer="Mashal Sports",
                gate_open_at=start_at - timedelta(hours=1),
                match_number=index + 1,
            )
        )

    return records


def build_badminton_events(reference_date: date) -> list[SportEvent]:
    records: list[SportEvent] = []
    base_date = max(reference_date + timedelta(days=110), date(2026, 10, 5))

    for index in range(12):
        home_team, away_team = BADMINTON_MATCHUPS[index % len(BADMINTON_MATCHUPS)]
        venue = BADMINTON_VENUES[index % len(BADMINTON_VENUES)]
        event_date = base_date + timedelta(days=index * 2)
        start_at = datetime.combine(event_date, time(18, 30), tzinfo=IST)
        stage_cycle = ["Round of 16", "Quarter Final", "Semi Final", "Final"]
        stage = stage_cycle[index % len(stage_cycle)]

        records.append(
            SportEvent(
                listing_code=f"SPT-BDM-{index + 1:03d}",
                title=f"{home_team} vs {away_team}",
                event_date=event_date,
                start_at=start_at,
                end_at=start_at + timedelta(hours=1, minutes=30),
                city=venue["city"],
                state=venue["state"],
                venue_name=venue["venue_name"],
                venue_area=venue["venue_area"],
                venue_address=venue["venue_address"],
                languages=["English", "Hindi"],
                min_price=249,
                max_price=999,
                tags=["badminton", "indoor", "singles", "synthetic"],
                metadata={"seed_origin": "synthetic"},
                source_label="synthetic",
                sport_type="Badminton",
                tournament_name="India Masters Badminton Series 2026",
                season_label="2026",
                competition_stage=stage,
                format_label="Best of 3 games",
                home_team=home_team,
                away_team=away_team,
                participant_names=[home_team, away_team],
                featured_athletes=[home_team, away_team],
                organizer="Badminton Association of India",
                gate_open_at=start_at - timedelta(minutes=45),
                match_number=index + 1,
            )
        )

    return records
