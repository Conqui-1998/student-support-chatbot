const path = require('path')
const lti = require('ltijs').Provider

const setup = async () => {
  await lti.setup('super-secret-key', {
    url: process.env.DATABASE_URL
  }, {
    appRoute: '/',
    loginRoute: '/login',
    keysetRoute: '/keys'
  })

  await lti.registerPlatform({
    url: 'https://moodle-demo.kent.ac.uk',
    name: 'My Moodle',
    clientId: 'smbfAvsM8OcKdqY',
    authenticationEndpoint: 'https://moodle-demo.kent.ac.uk/extra-demo/mod/lti/auth.php',
    accesstokenEndpoint: 'https://moodle-demo.kent.ac.uk/extra-demo/mod/lti/token.php',
    authConfig: {
      method: 'JWK_SET',
      key: 'https://moodle-demo.kent.ac.uk/extra-demo/mod/lti/certs.php'
    }
  })

  lti.onConnect((token, req, res) => {
    console.log('LTI user:', token.user)
    console.log('Course:', token.platformContext?.context?.id)

    res.sendFile(path.join(__dirname, 'public', 'index.html'))
  })

  await lti.deploy({ port: process.env.PORT || 3000 })
}

setup()