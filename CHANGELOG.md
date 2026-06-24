# Changelog

## [0.3.0](https://github.com/AlexanderBarabanov/physicalai/compare/v0.2.0...v0.3.0) (2026-06-24)


### ✨ Features

* add a universal resize preprocessing node ([#149](https://github.com/AlexanderBarabanov/physicalai/issues/149)) ([b0663da](https://github.com/AlexanderBarabanov/physicalai/commit/b0663da3c027c0138823b1d5b6f0955912fc9895))
* add from_config() and usage example ([#156](https://github.com/AlexanderBarabanov/physicalai/issues/156)) ([f479e9e](https://github.com/AlexanderBarabanov/physicalai/commit/f479e9eda6df39bdedd6c4606d8344de39c873f2))
* Add pre-commit checks ([#4](https://github.com/AlexanderBarabanov/physicalai/issues/4)) ([5dcf5e9](https://github.com/AlexanderBarabanov/physicalai/commit/5dcf5e9620d5a65d5b65b6b22133d7de5833b694))
* **capture:** add UVC camera capture ([#9](https://github.com/AlexanderBarabanov/physicalai/issues/9)) ([54c7b72](https://github.com/AlexanderBarabanov/physicalai/commit/54c7b721c7eef3d5841aca874876060d6f3ada3f))
* **cli:** add shared subcommand host for physicalai ([#142](https://github.com/AlexanderBarabanov/physicalai/issues/142)) ([8e463cb](https://github.com/AlexanderBarabanov/physicalai/commit/8e463cb93063465d76104dc162cee33111b079c0))
* **examples:** add e2e demo notebook ([#133](https://github.com/AlexanderBarabanov/physicalai/issues/133)) ([20bf8d6](https://github.com/AlexanderBarabanov/physicalai/commit/20bf8d69d1dc1e81a8252bfb4e56e5eede3dc98b))
* inference performance benchmark ([#134](https://github.com/AlexanderBarabanov/physicalai/issues/134)) ([bc3f760](https://github.com/AlexanderBarabanov/physicalai/commit/bc3f760ac3cc7aad75cda96a77cb74c31ef60b94))
* **repo:** sync repo with feature branch max/feature-robot-camera-pai ([#115](https://github.com/AlexanderBarabanov/physicalai/issues/115)) ([7166523](https://github.com/AlexanderBarabanov/physicalai/commit/7166523d7d85934f129fda09c0cc5de10ccb9a02))
* **robot:** SO101 implementation ([#3](https://github.com/AlexanderBarabanov/physicalai/issues/3)) ([2ccbe59](https://github.com/AlexanderBarabanov/physicalai/commit/2ccbe59e9386ce4d4cca04138f466b6a7fd3b29d))
* **runtime:** basic PolicyRuntime implementation ([#118](https://github.com/AlexanderBarabanov/physicalai/issues/118)) ([67b8b8e](https://github.com/AlexanderBarabanov/physicalai/commit/67b8b8e6087e90cd566b5e56f5e023c3636b02e7))
* **runtime:** callbacks, telemetry via rerun, fault tolerance ([#119](https://github.com/AlexanderBarabanov/physicalai/issues/119)) ([aae83d8](https://github.com/AlexanderBarabanov/physicalai/commit/aae83d83676183aefa2acc3a6cb2472431b6d3ff))
* **runtime:** implement Real-Time Chunking (RTC) execution strategy ([#128](https://github.com/AlexanderBarabanov/physicalai/issues/128)) ([3684019](https://github.com/AlexanderBarabanov/physicalai/commit/36840195186b5417cb619233aa1c48f1ccdc0ac9))


### 🐛 Bug Fixes

* align input type / layouts support across resize preprocessing nodes ([#162](https://github.com/AlexanderBarabanov/physicalai/issues/162)) ([f3ea7e6](https://github.com/AlexanderBarabanov/physicalai/commit/f3ea7e607587e65f1b4499c9827fc85f09e901b5))
* **capture:** add only_usable option  ([#139](https://github.com/AlexanderBarabanov/physicalai/issues/139)) ([c7144f4](https://github.com/AlexanderBarabanov/physicalai/commit/c7144f49d7ff15c19433cdcdb851dd1505154f36))
* correct download artifact action pin ([#140](https://github.com/AlexanderBarabanov/physicalai/issues/140)) ([75f0cd1](https://github.com/AlexanderBarabanov/physicalai/commit/75f0cd1f0a12726dfd42bf8896f7ecc2f66abb6f))
* **dep:** pin openvino and iceoryx2 versions ([#148](https://github.com/AlexanderBarabanov/physicalai/issues/148)) ([cdbd0de](https://github.com/AlexanderBarabanov/physicalai/commit/cdbd0ded42fd409dec3da5354b322694f2b286aa))
* **dep:** support for python 3.11 and error for missing intel XPU dependencies ([#150](https://github.com/AlexanderBarabanov/physicalai/issues/150)) ([34d03ab](https://github.com/AlexanderBarabanov/physicalai/commit/34d03ab2c43b64bc7f31e284490d972c47982f17))
* incorrect InferenceModel inputs with one camera setup ([#167](https://github.com/AlexanderBarabanov/physicalai/issues/167)) ([5848691](https://github.com/AlexanderBarabanov/physicalai/commit/58486917bddec243a79446d7332ca0ff7063afe1))
* missing mean iteration time in the perf benchmark ([#151](https://github.com/AlexanderBarabanov/physicalai/issues/151)) ([1e7ef0d](https://github.com/AlexanderBarabanov/physicalai/commit/1e7ef0d5c701a2bc0f18f8db4105c659ee51ec82))
* temporaly delete benchmark module to avoid conflicts with training lib ([#125](https://github.com/AlexanderBarabanov/physicalai/issues/125)) ([425fa82](https://github.com/AlexanderBarabanov/physicalai/commit/425fa8207cf150ab5ebe65cfdd1d87d9d3074e50))
* workaround missing ov extension failure ([#137](https://github.com/AlexanderBarabanov/physicalai/issues/137)) ([6ba5a84](https://github.com/AlexanderBarabanov/physicalai/commit/6ba5a840a54421594ed8bce97c7ed8c2bca3bb69))


### ♻️ Code Refactoring

* backport changes in inference package from PAS to this repo ([#120](https://github.com/AlexanderBarabanov/physicalai/issues/120)) ([7185d01](https://github.com/AlexanderBarabanov/physicalai/commit/7185d018d0b48742c4def2e91ac44060ef4b6ad8))
* delete traces of legacy metadata ([#127](https://github.com/AlexanderBarabanov/physicalai/issues/127)) ([011a4eb](https://github.com/AlexanderBarabanov/physicalai/commit/011a4eb1e0c33c3a811e185b6e881b8ceb2c2277))
* use dict in action chunk trim transform ([#124](https://github.com/AlexanderBarabanov/physicalai/issues/124)) ([0469898](https://github.com/AlexanderBarabanov/physicalai/commit/046989886183b0ff9b1361510c4baf89d1b5148a))


### 📚 Documentation

* add community health files ([0f99453](https://github.com/AlexanderBarabanov/physicalai/commit/0f99453b34ccf6c1de540bba173564bf4d24d741))
* add community health files ([876719e](https://github.com/AlexanderBarabanov/physicalai/commit/876719ea9d7a46d2d36a8566b8969b943530f4b5))
* add packaging, naming, and market strategy document ([0b2e1a5](https://github.com/AlexanderBarabanov/physicalai/commit/0b2e1a5672b1271d92ad4618cf6f0b587187d098))
* add user-facing documentation ([#122](https://github.com/AlexanderBarabanov/physicalai/issues/122)) ([7833bec](https://github.com/AlexanderBarabanov/physicalai/commit/7833bec4aafeb4118e033b12c4f655be173ee106))
* hide root index from sidebar using unlisted frontmatter ([d6bd69c](https://github.com/AlexanderBarabanov/physicalai/commit/d6bd69ca64ad7e08b24e6ed474df590176138ce6))
* **notebook:** move notebook and add readme ([#144](https://github.com/AlexanderBarabanov/physicalai/issues/144)) ([8dd0799](https://github.com/AlexanderBarabanov/physicalai/commit/8dd0799b5d0f2cfe18a8b28354db67abba5c60d2))
* **notebook:** update e2e notebook ([#143](https://github.com/AlexanderBarabanov/physicalai/issues/143)) ([44da137](https://github.com/AlexanderBarabanov/physicalai/commit/44da137d5015e7f62ce566158e0a87cd56303c62))
* **reamed:** update gif ([#153](https://github.com/AlexanderBarabanov/physicalai/issues/153)) ([7a378b8](https://github.com/AlexanderBarabanov/physicalai/commit/7a378b816c86337dc9df90e03c19e3169a5f2342))
* robot interface ([92f6b79](https://github.com/AlexanderBarabanov/physicalai/commit/92f6b79ba331ed5820b68b576bb2b82b2315aaa5))
* update banner image to include OpenVINO ([#154](https://github.com/AlexanderBarabanov/physicalai/issues/154)) ([b795346](https://github.com/AlexanderBarabanov/physicalai/commit/b795346a37f68539a6c8e130424589b2f20f0e7e))
* update camera interface design ([3235935](https://github.com/AlexanderBarabanov/physicalai/commit/3235935e26a216fda0cc88f33966a93acd5c246d))
* update packaging strategy for physical-ai and physical-ai-studio ([5c62ed5](https://github.com/AlexanderBarabanov/physicalai/commit/5c62ed53d49d44741c664d97162411431f917163))
* Update README.md ([00da975](https://github.com/AlexanderBarabanov/physicalai/commit/00da9750534cf982409209cf93c7f232378ed98f))
* Update README.md ([c302321](https://github.com/AlexanderBarabanov/physicalai/commit/c30232142ebc33084a25f6f12ed61dca2428d40c))
* update RTC execution defaults and add update docstring ([#155](https://github.com/AlexanderBarabanov/physicalai/issues/155)) ([e3f2828](https://github.com/AlexanderBarabanov/physicalai/commit/e3f28285e9e2647c50baf17ee0b33614cbe29e7e))
* update sidebar ordering and hide root index ([9219d4e](https://github.com/AlexanderBarabanov/physicalai/commit/9219d4e5d44ea6259bad266ef972164aed13b16f))
* update sidebar ordering and hide root index ([728cd3d](https://github.com/AlexanderBarabanov/physicalai/commit/728cd3da26e8a0dfc289e9480648cadc5f72defa))
* Update SUPPORT.md ([85694c9](https://github.com/AlexanderBarabanov/physicalai/commit/85694c94ac3aed63d0e27645dcd5766e077e4a97))


### 🔧 Chores

* add input validation ([#126](https://github.com/AlexanderBarabanov/physicalai/issues/126)) ([df8acb0](https://github.com/AlexanderBarabanov/physicalai/commit/df8acb0b57059f77c17c73d85b6ccf571c503fa2))
* add release readiness workflows ([#138](https://github.com/AlexanderBarabanov/physicalai/issues/138)) ([98f183e](https://github.com/AlexanderBarabanov/physicalai/commit/98f183e2445f6c9971d4cb668c629193db611085))
* bootstrap physicalai runtime repo ([7d7d898](https://github.com/AlexanderBarabanov/physicalai/commit/7d7d898bc1738b01f7336d0a31b39cb06e84ef1c))
* bump version to 0.2.0.dev0 ([#145](https://github.com/AlexanderBarabanov/physicalai/issues/145)) ([9995024](https://github.com/AlexanderBarabanov/physicalai/commit/99950244d792f051ad6df6592d9bed0d97561923))
* **ci:** add `dependency-review-action` config ([#163](https://github.com/AlexanderBarabanov/physicalai/issues/163)) ([d4a8655](https://github.com/AlexanderBarabanov/physicalai/commit/d4a8655f0446cf676d125bdf4d5f1c795e23f497))
* **ci:** enable Renovate ([a4ac1d2](https://github.com/AlexanderBarabanov/physicalai/commit/a4ac1d2319e6409924dce2a36d031435e7361255))
* **ci:** enable secret scanning ([#113](https://github.com/AlexanderBarabanov/physicalai/issues/113)) ([9b6ee0b](https://github.com/AlexanderBarabanov/physicalai/commit/9b6ee0b3d0184f56ac67ac6b75042c6e95c64a41))
* **ci:** security workflows minor updates ([52c6914](https://github.com/AlexanderBarabanov/physicalai/commit/52c6914abb083fba918c35e612120129107a0a5b))
* **ci:** update security workflows ([#117](https://github.com/AlexanderBarabanov/physicalai/issues/117)) ([48b5fd1](https://github.com/AlexanderBarabanov/physicalai/commit/48b5fd13b9defc77f353ce429b1312f532cffce3))
* delete leftover ActionChunking runner implementation ([#132](https://github.com/AlexanderBarabanov/physicalai/issues/132)) ([d721b12](https://github.com/AlexanderBarabanov/physicalai/commit/d721b12a0d351ef35b9ae385ab8850ea2545c3c4))
* **deps:** bump tornado from 6.5.6 to 6.5.7 ([#165](https://github.com/AlexanderBarabanov/physicalai/issues/165)) ([ab028df](https://github.com/AlexanderBarabanov/physicalai/commit/ab028df86569204c9edcfac7bb56d6b8090f6434))
* **deps:** lock file maintenance ([#112](https://github.com/AlexanderBarabanov/physicalai/issues/112)) ([e51a0ca](https://github.com/AlexanderBarabanov/physicalai/commit/e51a0ca00afb5fd7f85ee4e983e0fd178b94818e))
* **deps:** lock file maintenance ([#116](https://github.com/AlexanderBarabanov/physicalai/issues/116)) ([2b3a4ba](https://github.com/AlexanderBarabanov/physicalai/commit/2b3a4ba7d4ff06389c710a7c51843669b884f106))
* **deps:** lock file maintenance ([#146](https://github.com/AlexanderBarabanov/physicalai/issues/146)) ([ada3523](https://github.com/AlexanderBarabanov/physicalai/commit/ada35234bd8318179cba1bbee2485b99ba8e22ba))
* **deps:** lock file maintenance ([#157](https://github.com/AlexanderBarabanov/physicalai/issues/157)) ([d59a4ba](https://github.com/AlexanderBarabanov/physicalai/commit/d59a4bad8176f24f685405a96514ed5de4c39230))
* **deps:** update github actions ([96ea4f3](https://github.com/AlexanderBarabanov/physicalai/commit/96ea4f377334384a82ae8407c9c038c4d22311ff))
* **deps:** update github actions ([2731b6d](https://github.com/AlexanderBarabanov/physicalai/commit/2731b6d591e65fe6702c4302664e9693940043e0))
* **deps:** update github actions ([#114](https://github.com/AlexanderBarabanov/physicalai/issues/114)) ([ec34c9a](https://github.com/AlexanderBarabanov/physicalai/commit/ec34c9acffa58b1ad67692a4db0a4d2a4fa134d0))
* **deps:** update github actions ([#147](https://github.com/AlexanderBarabanov/physicalai/issues/147)) ([512efa6](https://github.com/AlexanderBarabanov/physicalai/commit/512efa6b17366ffb99ce0e4dff1ac6f97d21e9cd))
* **deps:** update github actions ([#161](https://github.com/AlexanderBarabanov/physicalai/issues/161)) ([b671f52](https://github.com/AlexanderBarabanov/physicalai/commit/b671f52f4c39b612916008f1cc9f66ae66dae763))
* enable blank issues ([53418c3](https://github.com/AlexanderBarabanov/physicalai/commit/53418c3bd5f9072c7c1f2725e32f13b12252d5fd))
* fix prek issues ([57290e4](https://github.com/AlexanderBarabanov/physicalai/commit/57290e45c1db9124d928c1aecd264df0a443aeb7))
* **main:** release physicalai 0.2.0 ([0659864](https://github.com/AlexanderBarabanov/physicalai/commit/065986401865129dc747ffa5386b7546b7055f02))
* **main:** release physicalai 0.2.0 ([7fe7647](https://github.com/AlexanderBarabanov/physicalai/commit/7fe7647841a49c7aaffb4d0eda7d4417c6931ab2))
* **physicalai:** copy source code from PAI studio ([#107](https://github.com/AlexanderBarabanov/physicalai/issues/107)) ([9094d6b](https://github.com/AlexanderBarabanov/physicalai/commit/9094d6b0ebd822ebf0049ab9117d4d8a0977f01a))
* set version to bug fix release 0.1.1 ([#152](https://github.com/AlexanderBarabanov/physicalai/issues/152)) ([1fd9a99](https://github.com/AlexanderBarabanov/physicalai/commit/1fd9a9956aa3fbf640c467245a824dd8b01c2d6a))
* sync code with physical-ai-studio ([#11](https://github.com/AlexanderBarabanov/physicalai/issues/11)) ([4a91e2f](https://github.com/AlexanderBarabanov/physicalai/commit/4a91e2f8d9937f1599e11dcba96d029eaf67a80f))
* update codeowners ([#136](https://github.com/AlexanderBarabanov/physicalai/issues/136)) ([76f129a](https://github.com/AlexanderBarabanov/physicalai/commit/76f129a920a0f7a62178b3b7873a30e67c068104))
* update security.md in codeowners ([ce2014e](https://github.com/AlexanderBarabanov/physicalai/commit/ce2014ec9b3f790ae9a2111071c92452ad0253bd))
* update security.md with standard intel text ([dcc89b8](https://github.com/AlexanderBarabanov/physicalai/commit/dcc89b829d5a9859847db82abd9ea37649edde2b))
* Update test_telemetry.py ([b049659](https://github.com/AlexanderBarabanov/physicalai/commit/b0496597cc9ebe84e36fa9bf7e8bb92c3a5a448e))

## [0.2.0](https://github.com/AlexanderBarabanov/physicalai/compare/physicalai-v0.1.1...physicalai-v0.2.0) (2026-06-24)


### ✨ Features

* add a universal resize preprocessing node ([#149](https://github.com/AlexanderBarabanov/physicalai/issues/149)) ([b0663da](https://github.com/AlexanderBarabanov/physicalai/commit/b0663da3c027c0138823b1d5b6f0955912fc9895))
* add from_config() and usage example ([#156](https://github.com/AlexanderBarabanov/physicalai/issues/156)) ([f479e9e](https://github.com/AlexanderBarabanov/physicalai/commit/f479e9eda6df39bdedd6c4606d8344de39c873f2))
* Add pre-commit checks ([#4](https://github.com/AlexanderBarabanov/physicalai/issues/4)) ([5dcf5e9](https://github.com/AlexanderBarabanov/physicalai/commit/5dcf5e9620d5a65d5b65b6b22133d7de5833b694))
* **capture:** add UVC camera capture ([#9](https://github.com/AlexanderBarabanov/physicalai/issues/9)) ([54c7b72](https://github.com/AlexanderBarabanov/physicalai/commit/54c7b721c7eef3d5841aca874876060d6f3ada3f))
* **cli:** add shared subcommand host for physicalai ([#142](https://github.com/AlexanderBarabanov/physicalai/issues/142)) ([8e463cb](https://github.com/AlexanderBarabanov/physicalai/commit/8e463cb93063465d76104dc162cee33111b079c0))
* **examples:** add e2e demo notebook ([#133](https://github.com/AlexanderBarabanov/physicalai/issues/133)) ([20bf8d6](https://github.com/AlexanderBarabanov/physicalai/commit/20bf8d69d1dc1e81a8252bfb4e56e5eede3dc98b))
* inference performance benchmark ([#134](https://github.com/AlexanderBarabanov/physicalai/issues/134)) ([bc3f760](https://github.com/AlexanderBarabanov/physicalai/commit/bc3f760ac3cc7aad75cda96a77cb74c31ef60b94))
* **repo:** sync repo with feature branch max/feature-robot-camera-pai ([#115](https://github.com/AlexanderBarabanov/physicalai/issues/115)) ([7166523](https://github.com/AlexanderBarabanov/physicalai/commit/7166523d7d85934f129fda09c0cc5de10ccb9a02))
* **robot:** SO101 implementation ([#3](https://github.com/AlexanderBarabanov/physicalai/issues/3)) ([2ccbe59](https://github.com/AlexanderBarabanov/physicalai/commit/2ccbe59e9386ce4d4cca04138f466b6a7fd3b29d))
* **runtime:** basic PolicyRuntime implementation ([#118](https://github.com/AlexanderBarabanov/physicalai/issues/118)) ([67b8b8e](https://github.com/AlexanderBarabanov/physicalai/commit/67b8b8e6087e90cd566b5e56f5e023c3636b02e7))
* **runtime:** callbacks, telemetry via rerun, fault tolerance ([#119](https://github.com/AlexanderBarabanov/physicalai/issues/119)) ([aae83d8](https://github.com/AlexanderBarabanov/physicalai/commit/aae83d83676183aefa2acc3a6cb2472431b6d3ff))
* **runtime:** implement Real-Time Chunking (RTC) execution strategy ([#128](https://github.com/AlexanderBarabanov/physicalai/issues/128)) ([3684019](https://github.com/AlexanderBarabanov/physicalai/commit/36840195186b5417cb619233aa1c48f1ccdc0ac9))


### 🐛 Bug Fixes

* align input type / layouts support across resize preprocessing nodes ([#162](https://github.com/AlexanderBarabanov/physicalai/issues/162)) ([f3ea7e6](https://github.com/AlexanderBarabanov/physicalai/commit/f3ea7e607587e65f1b4499c9827fc85f09e901b5))
* **capture:** add only_usable option  ([#139](https://github.com/AlexanderBarabanov/physicalai/issues/139)) ([c7144f4](https://github.com/AlexanderBarabanov/physicalai/commit/c7144f49d7ff15c19433cdcdb851dd1505154f36))
* correct download artifact action pin ([#140](https://github.com/AlexanderBarabanov/physicalai/issues/140)) ([75f0cd1](https://github.com/AlexanderBarabanov/physicalai/commit/75f0cd1f0a12726dfd42bf8896f7ecc2f66abb6f))
* **dep:** pin openvino and iceoryx2 versions ([#148](https://github.com/AlexanderBarabanov/physicalai/issues/148)) ([cdbd0de](https://github.com/AlexanderBarabanov/physicalai/commit/cdbd0ded42fd409dec3da5354b322694f2b286aa))
* **dep:** support for python 3.11 and error for missing intel XPU dependencies ([#150](https://github.com/AlexanderBarabanov/physicalai/issues/150)) ([34d03ab](https://github.com/AlexanderBarabanov/physicalai/commit/34d03ab2c43b64bc7f31e284490d972c47982f17))
* incorrect InferenceModel inputs with one camera setup ([#167](https://github.com/AlexanderBarabanov/physicalai/issues/167)) ([5848691](https://github.com/AlexanderBarabanov/physicalai/commit/58486917bddec243a79446d7332ca0ff7063afe1))
* missing mean iteration time in the perf benchmark ([#151](https://github.com/AlexanderBarabanov/physicalai/issues/151)) ([1e7ef0d](https://github.com/AlexanderBarabanov/physicalai/commit/1e7ef0d5c701a2bc0f18f8db4105c659ee51ec82))
* temporaly delete benchmark module to avoid conflicts with training lib ([#125](https://github.com/AlexanderBarabanov/physicalai/issues/125)) ([425fa82](https://github.com/AlexanderBarabanov/physicalai/commit/425fa8207cf150ab5ebe65cfdd1d87d9d3074e50))
* workaround missing ov extension failure ([#137](https://github.com/AlexanderBarabanov/physicalai/issues/137)) ([6ba5a84](https://github.com/AlexanderBarabanov/physicalai/commit/6ba5a840a54421594ed8bce97c7ed8c2bca3bb69))


### ♻️ Code Refactoring

* backport changes in inference package from PAS to this repo ([#120](https://github.com/AlexanderBarabanov/physicalai/issues/120)) ([7185d01](https://github.com/AlexanderBarabanov/physicalai/commit/7185d018d0b48742c4def2e91ac44060ef4b6ad8))
* delete traces of legacy metadata ([#127](https://github.com/AlexanderBarabanov/physicalai/issues/127)) ([011a4eb](https://github.com/AlexanderBarabanov/physicalai/commit/011a4eb1e0c33c3a811e185b6e881b8ceb2c2277))
* use dict in action chunk trim transform ([#124](https://github.com/AlexanderBarabanov/physicalai/issues/124)) ([0469898](https://github.com/AlexanderBarabanov/physicalai/commit/046989886183b0ff9b1361510c4baf89d1b5148a))


### 📚 Documentation

* add community health files ([0f99453](https://github.com/AlexanderBarabanov/physicalai/commit/0f99453b34ccf6c1de540bba173564bf4d24d741))
* add community health files ([876719e](https://github.com/AlexanderBarabanov/physicalai/commit/876719ea9d7a46d2d36a8566b8969b943530f4b5))
* add packaging, naming, and market strategy document ([0b2e1a5](https://github.com/AlexanderBarabanov/physicalai/commit/0b2e1a5672b1271d92ad4618cf6f0b587187d098))
* add user-facing documentation ([#122](https://github.com/AlexanderBarabanov/physicalai/issues/122)) ([7833bec](https://github.com/AlexanderBarabanov/physicalai/commit/7833bec4aafeb4118e033b12c4f655be173ee106))
* hide root index from sidebar using unlisted frontmatter ([d6bd69c](https://github.com/AlexanderBarabanov/physicalai/commit/d6bd69ca64ad7e08b24e6ed474df590176138ce6))
* **notebook:** move notebook and add readme ([#144](https://github.com/AlexanderBarabanov/physicalai/issues/144)) ([8dd0799](https://github.com/AlexanderBarabanov/physicalai/commit/8dd0799b5d0f2cfe18a8b28354db67abba5c60d2))
* **notebook:** update e2e notebook ([#143](https://github.com/AlexanderBarabanov/physicalai/issues/143)) ([44da137](https://github.com/AlexanderBarabanov/physicalai/commit/44da137d5015e7f62ce566158e0a87cd56303c62))
* **reamed:** update gif ([#153](https://github.com/AlexanderBarabanov/physicalai/issues/153)) ([7a378b8](https://github.com/AlexanderBarabanov/physicalai/commit/7a378b816c86337dc9df90e03c19e3169a5f2342))
* robot interface ([92f6b79](https://github.com/AlexanderBarabanov/physicalai/commit/92f6b79ba331ed5820b68b576bb2b82b2315aaa5))
* update banner image to include OpenVINO ([#154](https://github.com/AlexanderBarabanov/physicalai/issues/154)) ([b795346](https://github.com/AlexanderBarabanov/physicalai/commit/b795346a37f68539a6c8e130424589b2f20f0e7e))
* update camera interface design ([3235935](https://github.com/AlexanderBarabanov/physicalai/commit/3235935e26a216fda0cc88f33966a93acd5c246d))
* update packaging strategy for physical-ai and physical-ai-studio ([5c62ed5](https://github.com/AlexanderBarabanov/physicalai/commit/5c62ed53d49d44741c664d97162411431f917163))
* update RTC execution defaults and add update docstring ([#155](https://github.com/AlexanderBarabanov/physicalai/issues/155)) ([e3f2828](https://github.com/AlexanderBarabanov/physicalai/commit/e3f28285e9e2647c50baf17ee0b33614cbe29e7e))
* update sidebar ordering and hide root index ([9219d4e](https://github.com/AlexanderBarabanov/physicalai/commit/9219d4e5d44ea6259bad266ef972164aed13b16f))
* update sidebar ordering and hide root index ([728cd3d](https://github.com/AlexanderBarabanov/physicalai/commit/728cd3da26e8a0dfc289e9480648cadc5f72defa))
* Update SUPPORT.md ([85694c9](https://github.com/AlexanderBarabanov/physicalai/commit/85694c94ac3aed63d0e27645dcd5766e077e4a97))


### 🔧 Chores

* add input validation ([#126](https://github.com/AlexanderBarabanov/physicalai/issues/126)) ([df8acb0](https://github.com/AlexanderBarabanov/physicalai/commit/df8acb0b57059f77c17c73d85b6ccf571c503fa2))
* add release readiness workflows ([#138](https://github.com/AlexanderBarabanov/physicalai/issues/138)) ([98f183e](https://github.com/AlexanderBarabanov/physicalai/commit/98f183e2445f6c9971d4cb668c629193db611085))
* bootstrap physicalai runtime repo ([7d7d898](https://github.com/AlexanderBarabanov/physicalai/commit/7d7d898bc1738b01f7336d0a31b39cb06e84ef1c))
* bump version to 0.2.0.dev0 ([#145](https://github.com/AlexanderBarabanov/physicalai/issues/145)) ([9995024](https://github.com/AlexanderBarabanov/physicalai/commit/99950244d792f051ad6df6592d9bed0d97561923))
* **ci:** add `dependency-review-action` config ([#163](https://github.com/AlexanderBarabanov/physicalai/issues/163)) ([d4a8655](https://github.com/AlexanderBarabanov/physicalai/commit/d4a8655f0446cf676d125bdf4d5f1c795e23f497))
* **ci:** enable Renovate ([a4ac1d2](https://github.com/AlexanderBarabanov/physicalai/commit/a4ac1d2319e6409924dce2a36d031435e7361255))
* **ci:** enable secret scanning ([#113](https://github.com/AlexanderBarabanov/physicalai/issues/113)) ([9b6ee0b](https://github.com/AlexanderBarabanov/physicalai/commit/9b6ee0b3d0184f56ac67ac6b75042c6e95c64a41))
* **ci:** security workflows minor updates ([52c6914](https://github.com/AlexanderBarabanov/physicalai/commit/52c6914abb083fba918c35e612120129107a0a5b))
* **ci:** update security workflows ([#117](https://github.com/AlexanderBarabanov/physicalai/issues/117)) ([48b5fd1](https://github.com/AlexanderBarabanov/physicalai/commit/48b5fd13b9defc77f353ce429b1312f532cffce3))
* delete leftover ActionChunking runner implementation ([#132](https://github.com/AlexanderBarabanov/physicalai/issues/132)) ([d721b12](https://github.com/AlexanderBarabanov/physicalai/commit/d721b12a0d351ef35b9ae385ab8850ea2545c3c4))
* **deps:** bump tornado from 6.5.6 to 6.5.7 ([#165](https://github.com/AlexanderBarabanov/physicalai/issues/165)) ([ab028df](https://github.com/AlexanderBarabanov/physicalai/commit/ab028df86569204c9edcfac7bb56d6b8090f6434))
* **deps:** lock file maintenance ([#112](https://github.com/AlexanderBarabanov/physicalai/issues/112)) ([e51a0ca](https://github.com/AlexanderBarabanov/physicalai/commit/e51a0ca00afb5fd7f85ee4e983e0fd178b94818e))
* **deps:** lock file maintenance ([#116](https://github.com/AlexanderBarabanov/physicalai/issues/116)) ([2b3a4ba](https://github.com/AlexanderBarabanov/physicalai/commit/2b3a4ba7d4ff06389c710a7c51843669b884f106))
* **deps:** lock file maintenance ([#146](https://github.com/AlexanderBarabanov/physicalai/issues/146)) ([ada3523](https://github.com/AlexanderBarabanov/physicalai/commit/ada35234bd8318179cba1bbee2485b99ba8e22ba))
* **deps:** lock file maintenance ([#157](https://github.com/AlexanderBarabanov/physicalai/issues/157)) ([d59a4ba](https://github.com/AlexanderBarabanov/physicalai/commit/d59a4bad8176f24f685405a96514ed5de4c39230))
* **deps:** update github actions ([96ea4f3](https://github.com/AlexanderBarabanov/physicalai/commit/96ea4f377334384a82ae8407c9c038c4d22311ff))
* **deps:** update github actions ([2731b6d](https://github.com/AlexanderBarabanov/physicalai/commit/2731b6d591e65fe6702c4302664e9693940043e0))
* **deps:** update github actions ([#114](https://github.com/AlexanderBarabanov/physicalai/issues/114)) ([ec34c9a](https://github.com/AlexanderBarabanov/physicalai/commit/ec34c9acffa58b1ad67692a4db0a4d2a4fa134d0))
* **deps:** update github actions ([#147](https://github.com/AlexanderBarabanov/physicalai/issues/147)) ([512efa6](https://github.com/AlexanderBarabanov/physicalai/commit/512efa6b17366ffb99ce0e4dff1ac6f97d21e9cd))
* **deps:** update github actions ([#161](https://github.com/AlexanderBarabanov/physicalai/issues/161)) ([b671f52](https://github.com/AlexanderBarabanov/physicalai/commit/b671f52f4c39b612916008f1cc9f66ae66dae763))
* enable blank issues ([53418c3](https://github.com/AlexanderBarabanov/physicalai/commit/53418c3bd5f9072c7c1f2725e32f13b12252d5fd))
* fix prek issues ([57290e4](https://github.com/AlexanderBarabanov/physicalai/commit/57290e45c1db9124d928c1aecd264df0a443aeb7))
* **physicalai:** copy source code from PAI studio ([#107](https://github.com/AlexanderBarabanov/physicalai/issues/107)) ([9094d6b](https://github.com/AlexanderBarabanov/physicalai/commit/9094d6b0ebd822ebf0049ab9117d4d8a0977f01a))
* set version to bug fix release 0.1.1 ([#152](https://github.com/AlexanderBarabanov/physicalai/issues/152)) ([1fd9a99](https://github.com/AlexanderBarabanov/physicalai/commit/1fd9a9956aa3fbf640c467245a824dd8b01c2d6a))
* sync code with physical-ai-studio ([#11](https://github.com/AlexanderBarabanov/physicalai/issues/11)) ([4a91e2f](https://github.com/AlexanderBarabanov/physicalai/commit/4a91e2f8d9937f1599e11dcba96d029eaf67a80f))
* update codeowners ([#136](https://github.com/AlexanderBarabanov/physicalai/issues/136)) ([76f129a](https://github.com/AlexanderBarabanov/physicalai/commit/76f129a920a0f7a62178b3b7873a30e67c068104))
* update security.md in codeowners ([ce2014e](https://github.com/AlexanderBarabanov/physicalai/commit/ce2014ec9b3f790ae9a2111071c92452ad0253bd))
* update security.md with standard intel text ([dcc89b8](https://github.com/AlexanderBarabanov/physicalai/commit/dcc89b829d5a9859847db82abd9ea37649edde2b))
