package com.maxrave.domain.data.model.update

data class UpdateData(
    val tagName: String,
    val releaseTime: String?,
    val body: String,
    /** Direct download URL of the release's primary APK asset, when the release carries one. */
    val downloadUrl: String? = null,
)